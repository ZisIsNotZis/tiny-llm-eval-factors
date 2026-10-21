每个文件 = 一次真实请求的原始 JSON。chat_* 走生成类基准的端点，completions_* 走
对数似然类的端点（EchoShim 从 top_logprobs 读真 logprob）。差分判据见 RESULT.md。
两次请求都只改 server 启动参数 `--reasoning off|on`，提示词逐字相同。
