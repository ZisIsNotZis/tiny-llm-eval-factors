#!/bin/bash
# Negative control for `mpl_cell_audit.py`: prove the audit can see a report cell that
# belongs to another protocol row, and a printed item count that its artefact contradicts.
#
# The audit's [7] section makes two claims about every cell `report.html` prints: the
# row label must map to a stored protocol for that model and language, the value must be
# a stored value under that label, and the printed item count must be the artefact's.  A
# check that cannot fail proves nothing, so this script copies the report to a scratch
# directory and corrupts it twice:
#   1. gemma-4-12b Q2's cpp chat value (0.0248, which exists only under
#      `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`) is moved into that model's
#      `raw` row, so the value is stored but under another protocol;
#   2. a printed `(161)` becomes `(160)` on a cell that exists exactly once, so the
#      value is right and the item count it claims is not;
#   3. a stored protocol gains a `;ctx=99999` field its summary never had;
#   4. a per-item artefact that raised on every item gets a stored `0.0` back, so a
#      non-measurement claims to be a score -- and, on the other side of the same
#      section, every `;corpus=` row must still trace to a14's regrade ledger (the
#      clean run asserts the 12 regrade traces, so a green run means those rows were
#      not silently dropped from the lineage check).
#
# Run from the repository root:
#
#   bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"
#
# Exit 0 = the clean report passed and both corrupted copies were rejected.  Exit 1 = the
# control itself failed (the audit missed a corruption): that is a finding about the
# audit, not about the report.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AUDIT="$REPO/docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== clean run"
python3 "$AUDIT" > "$WORK/clean.txt" 2>&1
CLEAN=$?
tail -2 "$WORK/clean.txt"
echo "exit=$CLEAN"

echo "== corrupt case 1: gemma-4-12b Q2 cpp = 0.0248 inside the 'raw' row"
python3 - "$REPO/report.html" "$WORK/report_proto.html" <<'INJECT'
import sys

src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding="utf-8").read()
row = "<tr><td>gemma-4-12b-it-UD-Q2_K_XL.gguf</td><td>raw</td>"
i = h.find(row)
assert i > 0, "the gemma-4-12b Q2 raw row is not in the report"
start = i + len(row)
first = h.find("<td", start)
end = h.find("</td>", first) + len("</td>")
print("  replacing %r with the chat value" % h[first:end])
open(dst, "w", encoding="utf-8").write(
    h[:first] + "<td>0.0248 <span class='nr'>(161)</span></td>" + h[end:])
INJECT
python3 "$AUDIT" --report "$WORK/report_proto.html" > "$WORK/corrupt_proto.txt" 2>&1
CORRUPT_PROTO=$?
sed -n '/\[7\]/,/\[8\]/p' "$WORK/corrupt_proto.txt"
echo "exit=$CORRUPT_PROTO"

echo "== corrupt case 2: gemma-4-12b Q2 py chat prints (160) instead of (161)"
python3 - "$REPO/report.html" "$WORK/report_n.html" <<'INJECT'
import sys

src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding="utf-8").read()
row = "<tr><td>gemma-4-12b-it-UD-Q2_K_XL.gguf</td><td>chat</td>"
i = h.find(row)
assert i > 0, "the gemma-4-12b Q2 chat row is not in the report"
start = i + len(row)
j = h.find("(161)", start)
assert 0 < j - start < 400, "the chat row does not print (161) among its own cells"
print("  replacing the first '(161)' in that row")
open(dst, "w", encoding="utf-8").write(h[:j] + "(160)" + h[j + len("(161)"):])
INJECT
python3 "$AUDIT" --report "$WORK/report_n.html" > "$WORK/corrupt_n.txt" 2>&1
CORRUPT_N=$?
sed -n '/\[7\]/,/\[8\]/p' "$WORK/corrupt_n.txt"
echo "exit=$CORRUPT_N"

echo "== corrupt case 3: a stored protocol gains a ';' field its summary never had"
sqlite3 "$REPO/experiments.sqlite" ".backup '$WORK/db.sqlite'"
python3 - "$WORK/db.sqlite" <<'INJECT'
import sqlite3
import sys

con = sqlite3.connect(sys.argv[1])
cur = con.execute(
    "UPDATE experiments SET protocol = protocol || ';ctx=99999' "
    "WHERE model='Bonsai-27B-Q1_0.gguf' AND language='cpp' "
    "AND protocol='multipl-e-raw-greedy-768'")
print("  rows changed: %d" % cur.rowcount)
con.commit()
con.close()
INJECT
python3 "$AUDIT" --db "$WORK/db.sqlite" > "$WORK/corrupt_db.txt" 2>&1
CORRUPT_DB=$?
sed -n '/\[9\]/,/\[10\]/p' "$WORK/corrupt_db.txt"
if grep -q "RELABELLED" "$WORK/corrupt_db.txt"; then
  echo "  [9] reported the injected field (RELABELLED present)"
else
  echo "  [9] did NOT report the injected field"
  CORRUPT_DB=0
fi
echo "exit=$CORRUPT_DB"

echo "== corrupt case 4: a cell whose artefact raised on every item gets a stored 0.0"
sqlite3 "$REPO/experiments.sqlite" ".backup '$WORK/db_zero.sqlite'"
python3 - "$WORK/db_zero.sqlite" <<'INJECT'
import sqlite3
import sys

# The canonical gemma-4-12b Q2 js cell is NULL because all 161 items raised.  Writing
# 0.0 back is exactly the defect the rule forbids: a non-measurement claiming a score.
con = sqlite3.connect(sys.argv[1])
cur = con.execute(
    "UPDATE experiments SET _score = 0.0 WHERE model='gemma-4-12b-it-UD-Q2_K_XL.gguf' "
    "AND language='js' AND protocol='multipl-e-raw-greedy-768' AND _score IS NULL")
print("  rows changed: %d" % cur.rowcount)
con.commit()
con.close()
INJECT
python3 "$AUDIT" --db "$WORK/db_zero.sqlite" > "$WORK/corrupt_zero.txt" 2>&1
CORRUPT_ZERO=$?
sed -n '/all-Exception/,+2p' "$WORK/corrupt_zero.txt"
if grep -q "gemma-4-12b-it-UD-Q2_K_XL.gguf *js" "$WORK/corrupt_zero.txt"; then
  echo "  [4] reported the zeroed non-measurement and named the cell"
else
  echo "  [4] did NOT name the zeroed non-measurement"
  CORRUPT_ZERO=0
fi
echo "exit=$CORRUPT_ZERO"

echo "== normal regrade rows (the other half of case 4: they must stay traced)"
if grep -q "via a14 regrade 12" "$WORK/clean.txt"; then
  echo "  clean run traced 12 rows to a14's regrade ledger"
  REGRADE_OK=0
else
  echo "  clean run did NOT report 12 regrade traces"
  grep -m2 "scored cells traced" "$WORK/clean.txt"
  REGRADE_OK=1
fi

echo "== verdict"
if [ "$CLEAN" -eq 0 ] && [ "$REGRADE_OK" -eq 0 ] && [ "$CORRUPT_PROTO" -ne 0 ] \
   && [ "$CORRUPT_N" -ne 0 ] && [ "$CORRUPT_DB" -ne 0 ] && [ "$CORRUPT_ZERO" -ne 0 ]; then
  echo "PASS: clean run accepted (exit 0) with 12 regrade traces; protocol-row corruption rejected (exit $CORRUPT_PROTO); item-count corruption rejected (exit $CORRUPT_N); injected ';' field rejected (exit $CORRUPT_DB); zeroed non-measurement rejected (exit $CORRUPT_ZERO)"
  exit 0
fi
echo "FAIL: clean exit=$CLEAN, regrade traces=$REGRADE_OK, protocol corruption exit=$CORRUPT_PROTO, item-count corruption exit=$CORRUPT_N, db-protocol corruption exit=$CORRUPT_DB, zeroed non-measurement exit=$CORRUPT_ZERO"
exit 1
