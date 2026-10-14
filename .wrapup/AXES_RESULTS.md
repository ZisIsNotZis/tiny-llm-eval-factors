# AXES results (auto-updated 2026-10-14T06:52:34+08:00)

complete tags: 12/12

## axes_findings.py
================================================================================================================
AXIS 1.6  QAT vs NATIVE at the same nominal UD-Q?_K_XL recipe (delta = qat - native, +favours QAT)
================================================================================================================

gemma-4-12B-it  UD-Q4_K_XL   bpw qat=4.512 native=4.949 (d=-0.437)   [6/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       -0.0061 [-0.0675,+0.0553]  164/164  
  mbpp-plus            -0.0106 [-0.0735,+0.0523]  378/378  
  mmlu                 -0.1974 [-0.2422,-0.1526]  912/912  
  arc_challenge        pending
  truthfulqa_mc2       +0.0255 [-0.1129,+0.1640]  100/100  
  gsm8k                +0.0200 [-0.0458,+0.0858]  100/100  
  ifeval               -0.0200 [-0.1067,+0.0667]  100/100  

gemma-4-31B-it  UD-Q4_K_XL   bpw qat=4.505 native=4.905 (d=-0.400)   [0/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       pending
  mbpp-plus            pending
  mmlu                 pending
  arc_challenge        pending
  truthfulqa_mc2       pending
  gsm8k                pending
  ifeval               pending

gemma-4-26B-A4B-it  UD-Q4_K_XL   bpw qat=4.518 native=5.393 (d=-0.876)   [0/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       pending
  mbpp-plus            pending
  mmlu                 pending
  arc_challenge        pending
  truthfulqa_mc2       pending
  gsm8k                pending
  ifeval               pending

gemma-4-E2B-it  UD-Q4_K_XL   bpw qat=4.529 native=5.482 (d=-0.953)   [7/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       +0.0061 [-0.0927,+0.1049]  164/164  
  mbpp-plus            +0.0344 [-0.0369,+0.1056]  378/378  
  mmlu                 +0.0055 [-0.0398,+0.0508]  912/912  
  arc_challenge        -0.0200 [-0.1585,+0.1185]  100/100  
  truthfulqa_mc2       -0.0208 [-0.1593,+0.1178]  100/100  
  gsm8k                -0.0400 [-0.1565,+0.0765]  100/100  
  ifeval               -0.0200 [-0.1444,+0.1044]  100/100  

gemma-4-E2B-it  UD-Q2_K_XL   bpw qat=3.779 native=4.138 (d=-0.359)   [5/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       -0.3110 [-0.4090,-0.2129]  164/164  
  mbpp-plus            pending
  mmlu                 -0.0296 [-0.0753,+0.0161]  912/912  
  arc_challenge        pending
  truthfulqa_mc2       +0.0466 [-0.0913,+0.1845]  100/100  
  gsm8k                -0.2900 [-0.4226,-0.1574]  100/100  
  ifeval               -0.1700 [-0.3066,-0.0334]  100/100  

gemma-4-E4B-it  UD-Q4_K_XL   bpw qat=4.519 native=5.455 (d=-0.936)   [7/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       +0.0366 [-0.0529,+0.1261]  164/164  
  mbpp-plus            +0.0556 [-0.0131,+0.1242]  378/378  
  mmlu                 +0.0132 [-0.0286,+0.0549]  912/912  
  arc_challenge        +0.0300 [-0.1085,+0.1685]  100/100  
  truthfulqa_mc2       -0.0141 [-0.1503,+0.1221]  100/100  
  gsm8k                +0.0500 [-0.0501,+0.1501]  100/100  
  ifeval               -0.0500 [-0.1574,+0.0574]  100/100  

gemma-4-E4B-it  UD-Q2_K_XL   bpw qat=3.451 native=3.998 (d=-0.547)   [7/7 benches]
  bench             qat-native                 95% CI    n_t/n_c
  humaneval-plus       -0.1646 [-0.2686,-0.0607]  164/164  
  mbpp-plus            -0.2116 [-0.2812,-0.1421]  378/378  
  mmlu                 -0.1502 [-0.1951,-0.1054]  912/912  
  arc_challenge        -0.1100 [-0.2452,+0.0252]  100/100  
  truthfulqa_mc2       +0.0598 [-0.0779,+0.1975]  100/100  
  gsm8k                -0.3900 [-0.5111,-0.2689]  100/100  
  ifeval               -0.0600 [-0.1813,+0.0613]  100/100  

----------------------------------------------------------------------------------------------------------------
POOLED per benchmark (inverse-variance over complete pairs)
----------------------------------------------------------------------------------------------------------------
  bench             mean delta                   95% CI  pairs
  humaneval-plus       -0.0639 [-0.1020,-0.0258]      5
  mbpp-plus            -0.0320 [-0.0660,+0.0019]      4
  mmlu                 -0.0698 [-0.0896,-0.0499]      5
  arc_challenge        -0.0346 [-0.1139,+0.0447]      3
  truthfulqa_mc2       +0.0193 [-0.0423,+0.0809]      5
  gsm8k                -0.0687 [-0.1122,-0.0253]      5
  ifeval               -0.0529 [-0.1025,-0.0033]      5

  overall UD-Q4_K_XL (5 pairs): pooled delta over all benchmark cells -0.0192 [-0.0357,-0.0026] (n=20 cells)

  overall UD-Q2_K_XL (2 pairs): pooled delta over all benchmark cells -0.1327 [-0.1563,-0.1090] (n=12 cells)

================================================================================================================
AXIS 1.5  GSQ-RCO vs the standard Qwen3.8-27B quant ladder (delta = gsq - native)
================================================================================================================
  native ladder: native UD-Q2_K_XL@2.878  native UD-Q3_K_XL@3.850  native UD-IQ4_XS@4.173

GSQ-RCO IQ3_XXS  effective bpw 3.058   nearest native native UD-Q2_K_XL@2.878 (d=+0.180)
  interpolating native ladder between native UD-Q2_K_XL@2.878 and native UD-Q3_K_XL@3.850
  bench                 gsq  near-native               d(nearest)                d(interp)
  humaneval-plus     0.8476       0.8963 [-0.1209,+0.0234] [-0.1096,+0.0346]
  mbpp-plus          0.7540       0.7619 [-0.0690,+0.0531] [-0.0646,+0.0575]
  mmlu               0.8103       0.8037 [-0.0296,+0.0428] [-0.0357,+0.0367]
  arc_challenge      0.6100       0.6100 [-0.1352,+0.1352] [-0.1315,+0.1389]
  truthfulqa_mc2     0.5733       0.5210 [-0.0855,+0.1901] [-0.0945,+0.1811]
  gsm8k              0.9400       0.9800 [-0.0940,+0.0140] [-0.0903,+0.0177]
  ifeval             0.8200       0.8300 [-0.1153,+0.0953] [-0.1005,+0.1101]

GSQ-RCO IQ3_S  effective bpw 3.549   nearest native native UD-Q3_K_XL@3.850 (d=-0.301)
  interpolating native ladder between native UD-Q2_K_XL@2.878 and native UD-Q3_K_XL@3.850
  bench                 gsq  near-native               d(nearest)                d(interp)
  humaneval-plus     0.8963       0.8354 [-0.0125,+0.1344] [-0.0314,+0.1156]
  mbpp-plus          0.7646       0.7381 [-0.0351,+0.0881] [-0.0425,+0.0807]
  mmlu               0.8279       0.8366 [-0.0431,+0.0255] [-0.0329,+0.0357]
  arc_challenge      0.6000       0.5900 [-0.1261,+0.1461] [-0.1322,+0.1399]
  truthfulqa_mc2     0.5499       0.5693 [-0.1570,+0.1182] [-0.1420,+0.1331]
  gsm8k              0.9600       0.9600 [-0.0543,+0.0543] [-0.0605,+0.0481]
  ifeval             0.8500       0.7500 [-0.0100,+0.2100] [-0.0348,+0.1853]

================================================================================================================
AXIS 7  DiffusionGemma vs same-size autoregressive gemma-4-26B-A4B
================================================================================================================
  treatment m154-diffusiongemma-26b-a4b-q4km: GATE-FAIL -- no local llama.cpp
            runtime accepts architecture 'diffusion-gemma' (gate log)
  control   m145-native-gemma26b-a4b-q4 (autoregressive): humaneval-plus=pending  mbpp-plus=pending  mmlu=pending  arc_challenge=pending  truthfulqa_mc2=pending  gsm8k=pending  ifeval=pending
  -> no axis-7 comparison exists until a runtime supports the diffusion arch.

wrote .wrapup/axes_findings.json

## axes_analysis.py

============================================================================================================
AXIS 1.6  QAT vs NATIVE, same size + same UD-Q?_K_XL recipe (positive = qat scores higher)
============================================================================================================
model                        humaneval-p   mbpp-plus        mmlu arc_challen truthfulqa_       gsm8k      ifeval
gemma-4-12B-it  UD-Q4_K_XL        0.9146      0.7407      0.6436     pending      0.5039      0.9300      0.9000  <- native
  m140-qat-gemma12b-q4            0.9085      0.7302      0.4463     pending      0.5295      0.9500      0.8800  <- QAT
  delta (qat-native)             -0.0061     -0.0106     -0.1974     pending     +0.0255     +0.0200     -0.0200
gemma-4-31B-it  UD-Q4_K_XL       pending     pending     pending     pending     pending     pending     pending  <- native
  m142-qat-gemma31b-q4           pending     pending     pending     pending     pending     pending     pending  <- QAT
  delta (qat-native)             pending     pending     pending     pending     pending     pending     pending
gemma-4-26B-A4B-it UD-Q4_K_XL     pending     pending     pending     pending     pending     pending     pending  <- native
  m144-qat-gemma26b-a4b-q4        0.9146      0.7698      0.7105     pending     pending      0.9600      0.8100  <- QAT
  delta (qat-native)             pending     pending     pending     pending     pending     pending     pending
gemma-4-E2B-it  UD-Q4_K_XL        0.7012      0.4815      0.5779      0.5000      0.5214      0.7900      0.7300  <- native
  m147-qat-gemma-e2b-q4           0.7073      0.5159      0.5833      0.4800      0.5006      0.7500      0.7100  <- QAT
  delta (qat-native)             +0.0061     +0.0344     +0.0055     -0.0200     -0.0208     -0.0400     -0.0200
gemma-4-E2B-it  UD-Q2_K_XL        0.5122      0.4339      0.4748      0.4200      0.4325      0.6300      0.5900  <- native
  m146-qat-gemma-e2b-q2           0.2012     pending      0.4452     pending      0.4791      0.3400      0.4200  <- QAT
  delta (qat-native)             -0.3110     pending     -0.0296     pending     +0.0466     -0.2900     -0.1700
gemma-4-E4B-it  UD-Q4_K_XL        0.7622      0.6032      0.7018      0.4800      0.5994      0.8200      0.8400  <- native
  m155-qat-gemma-e4b-q4           0.7988      0.6587      0.7149      0.5100      0.5853      0.8700      0.7900  <- QAT
  delta (qat-native)             +0.0366     +0.0556     +0.0132     +0.0300     -0.0141     +0.0500     -0.0500
gemma-4-E4B-it  UD-Q2_K_XL        0.6951      0.5820      0.6502      0.4600      0.5177      0.8400      0.7700  <- native
  m149-qat-gemma-e4b-q2           0.5305      0.3704      0.5000      0.3500      0.5775      0.4500      0.7100  <- QAT
  delta (qat-native)             -0.1646     -0.2116     -0.1502     -0.1100     +0.0598     -0.3900     -0.0600

============================================================================================================
AXIS 1.5  GSQ-RCO quantisation vs standard Qwen3.8-27B quants
============================================================================================================
quant                        humaneval-p   mbpp-plus        mmlu arc_challen truthfulqa_       gsm8k      ifeval
GSQ-RCO IQ3_XXS                   0.8476      0.7540      0.8103      0.6100      0.5733      0.9400      0.8200
GSQ-RCO IQ3_S                     0.8963      0.7646      0.8279      0.6000      0.5499      0.9600      0.8500
native UD-Q2_K_XL                 0.8963      0.7619      0.8037      0.6100      0.5210      0.9800      0.8300
native UD-Q3_K_XL                 0.8354      0.7381      0.8366      0.5900      0.5693      0.9600      0.7500
native UD-IQ4_XS                  0.8720      0.7593      0.8498      0.6000      0.5685      0.9800      0.7700

note                         GSQ-RCO is not paired 1:1 with a native quant; the standard Q2/Q3/IQ4_XS rows bracket it in bpw.

============================================================================================================
AXIS 7  DiffusionGemma vs same-size autoregressive gemma-4-26B-A4B
============================================================================================================
  treatment m154-diffusiongemma-26b-a4b-q4km: GATE-FAIL (runtime rejects architecture 'diffusion-gemma')
  control   m145-native-gemma26b-a4b-q4:       humaneval-plus=pending mbpp-plus=pending mmlu=pending arc_challenge=pending truthfulqa_mc2=pending gsm8k=pending ifeval=pending
  -> no axis-7 comparison exists until a runtime supports the diffusion architecture.
