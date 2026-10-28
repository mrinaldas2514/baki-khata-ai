# Parser evaluation: rules (rule-based)

- **Date:** 2026-10-28
- **Parser:** `rules`, model `rule-based`
- **Sentences:** 186 (186 from eval set), 176 expected entries
- **Command:** `python -m eval.run_eval --parser rules` (in `backend/`)

Each sentence goes through the same steps as `POST /parse` (number normalization, the parser, validation with one retry). A sentence is right only if every entry has the right customer name, amount, type and item, and nothing extra; a non-transaction is right only if the parser refuses it.

> **Errors:** 1 sentence(s) got no usable answer (`nt-06` invalid output). Counted as wrong, except 1 that should be refused anyway (the app then shows the manual form, so nothing wrong is saved).

## Summary

| Metric | Result |
|---|---|
| **All fields correct** (per sentence) | **90.3% (168/186)** |
| Customer name (per entry) | 97.7% (172/176) |
| Amount (per entry) | 97.7% (172/176) |
| Type (per entry) | 95.5% (168/176) |
| Item (per entry) | 90.9% (160/176) |
| Non-transactions refused | 87.5% (21/24) |
| Latency per sentence, average | 0.1 ms |
| Latency per sentence, p95 | 0.2 ms |

## By category

| Category | All fields correct |
|---|---|
| Banglish, baki | 100.0% (14/14) |
| Banglish, joma | 100.0% (13/13) |
| Bangla script | 100.0% (14/14) |
| English | 84.6% (11/13) |
| Code-mixed | 91.7% (11/12) |
| Number words (pach sho, dedh hajar...) | 93.8% (15/16) |
| Bangla digits | 100.0% (11/11) |
| Honorifics (bhai, apa, da...) | 93.3% (14/15) |
| Items | 100.0% (13/13) |
| Typos and missing spaces | 60.0% (9/15) |
| Past-tense payments (shodh korlo...) | 92.9% (13/14) |
| Several entries in one sentence | 75.0% (9/12) |
| No amount (should be refused) | 100.0% (12/12) |
| Not a transaction (should be refused) | 75.0% (9/12) |

## By language

| Language | All fields correct |
|---|---|
| bangla | 100.0% (30/30) |
| banglish | 88.7% (102/115) |
| english | 80.0% (16/20) |
| mixed | 95.2% (20/21) |

## Failures (18)

| Id | Text | Expected | Got | Wrong |
|---|---|---|---|---|
| en-06 | Jamal bought sugar and tea worth 300 on credit | Jamal · ৳300 · baki · sugar, tea | Jamal · ৳300 · baki · bought sugar, tea, on | item |
| en-10 | Put 450 on Tanvir's account for oil | Tanvir · ৳450 · baki · oil | Put · ৳450 · baki · on Tanvir s account, oil | name, item |
| mx-07 | jasim 2 kg chicken 380 taka credit e nilo | jasim · ৳380 · baki · 2 kg chicken | jasim · ৳380 · baki · 2 kg chicken, e | item |
| nw-09 | poune dui hajar taka baki rohim er | rohim · ৳1750 · baki | (refused: no customer name) | no entry |
| hn-06 | hasan mama 300 taka diye gelo | hasan · ৳300 · joma | hasan · ৳300 · baki · diye gelo | type, item |
| ty-01 | rhim bhai 300 tk bki | rhim · ৳300 · baki | rhim · ৳300 · baki · bki | item |
| ty-05 | rahim 150 bakki | rahim · ৳150 · baki | rahim · ৳150 · baki · bakki | item |
| ty-06 | Karim 400 dlo | Karim · ৳400 · joma | Karim · ৳400 · baki · dlo | type, item |
| ty-07 | nasir 250 tkaa jma | nasir · ৳250 · joma | nasir · ৳250 · baki · tkaa jma | type, item |
| ty-11 | monir 300 tk shod | monir · ৳300 · joma | monir · ৳300 · baki · shod | type, item |
| ty-13 | lipi 80 taka bakii, cha | lipi · ৳80 · baki · cha | lipi · ৳80 · baki · bakii, cha | item |
| pp-11 | tumpa 250 taka diye gese | tumpa · ৳250 · joma | tumpa · ৳250 · baki · diye gese | type, item |
| me-06 | Hasan paid 500 and Rina took 200 on credit | Hasan · ৳500 · joma + Rina · ৳200 · baki | Hasan · ৳500 · joma | name, amount, type, item, 1 entries, not 2 |
| me-08 | tuhin 100 r sumon 200 baki | tuhin · ৳100 · baki + sumon · ৳200 · baki | tuhin · ৳200 · baki · 100, sumon | amount, item, name, type, 1 entries, not 2 |
| me-10 | babu 50, rana 70, polash 90 sob baki | babu · ৳50 · baki + rana · ৳70 · baki + polash · ৳90 · baki | babu · ৳50 · baki + rana · ৳70 · baki + polash · ৳90 · baki · sob | item |
| nt-09 | Total sales today 5000 | (refuse: not a transaction) | Total · ৳5000 · baki · sales | should refuse |
| nt-10 | chal er dam 70 taka kg | (refuse: not a transaction) | chal · ৳70 · baki · dam, kg | should refuse |
| nt-11 | mal anar jonno 3000 taka lagbe | (refuse: not a transaction) | mal · ৳3000 · baki · anar jonno, lagbe | should refuse |
