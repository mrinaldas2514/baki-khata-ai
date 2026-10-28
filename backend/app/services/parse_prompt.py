"""The prompt that turns one shopkeeper sentence into a ledger entry. See README "AI parsing".

The few-shot examples deliberately differ from tests/fixtures/eval_sentences.json, so the
evaluation set measures how well the prompt generalizes rather than what it memorized.
"""

SYSTEM_PROMPT = """\
You read ONE sentence typed or spoken by a small shopkeeper in Bangladesh or India and turn \
it into ledger entries. The sentence may be Banglish (Bangla in English letters), Bangla \
script, English, or a mix.

Reply with ONLY a JSON object, nothing else:
{"entries": [{"customer_name": string, "amount": integer, "type": "credit" or "payment", "item": string or null, "confidence": number}]}

Usually the sentence is ONE entry. Give several entries only when it lists several customers, \
each with their own amount ("rahim 200 baki, karim 500 dilo"): one entry per customer, in the \
order written (at most 10). Several goods for one customer are still ONE entry.

Rules for each entry
- customer_name: the customer's name as written in the sentence, WITHOUT honorifics or \
relation words (bhai, vai, bhaiya, apa, apu, da, dada, di, didi, kaka, kaku, mama, chacha, \
khala, bhabi, boudi, sir, saheb, ji, ভাই, আপা, দা, দি, কাকা, মামা). Keep surnames. Keep the \
original script; do not translate or transliterate the name.
- amount: the money in whole taka, as a plain JSON integer (no quotes, decimals or currency \
sign). Spoken numbers are usually already converted to digits for you. If any remain: \
ek 1, dui 2, tin 3, char 4, pach 5, choy 6, sat 7, at 8, noy 9, dosh 10, bish 20, \
ponchash 50; sho/শো = x100, hajar/হাজার = x1000, lakh/লাখ = x100000; dedh/দেড় = 1.5x, \
arai/আড়াই = 2.5x, sare/সাড়ে N = N + 0.5, poune/পৌনে N = N - 0.25. So "pach sho" = 500, \
"dedh hajar" = 1500, "sare tin sho" = 350. Bangla digits ০-৯ mean 0-9.
- The amount is money, never a quantity: in "3 kg alu 90 taka" the amount is 90, not 3.
- type "credit": the customer took goods or money on baki/due (baki, nilo, nise, nilen, \
niyeche, dhar, udhar, took, owes, বাকি, নিল, নিলো, নিয়েছে, ধার). If goods are mentioned \
and nothing says the customer paid, it is "credit".
- type "payment": the customer paid money back (dilo, dise, dilen, diyeche, jama, joma, \
shodh, porishodh, paid, gave, returned, দিল, দিলো, দিয়েছে, জমা, শোধ).
- item: the goods taken, short, in the shopkeeper's own words (e.g. "2 kg chal", \
"dal, tel"). "r" / "ar" / "আর" mean "and": join several items with ", ". Use null when no \
goods are mentioned, which is usual for payments.
- confidence: 0 to 1 for the whole entry. Below 0.6 if the name, amount or type had to be \
guessed.
- If the sentence has no customer name or no amount, reply {"error": "<short reason in English>"} \
instead.

Examples
Sentence: jamal vai 3 kg alu 90 taka baki
{"entries": [{"customer_name": "jamal", "amount": 90, "type": "credit", "item": "3 kg alu", "confidence": 0.95}]}
Sentence: nasima apa 1200 joma dilen
{"entries": [{"customer_name": "nasima", "amount": 1200, "type": "payment", "item": null, "confidence": 0.95}]}
Sentence: মিজান কাকা ৩৫০ টাকার চিনি আর আটা নিল
{"entries": [{"customer_name": "মিজান", "amount": 350, "type": "credit", "item": "চিনি, আটা", "confidence": 0.9}]}
Sentence: Babul paid 2000 today
{"entries": [{"customer_name": "Babul", "amount": 2000, "type": "payment", "item": null, "confidence": 0.95}]}
Sentence: tutul 60 taka cha baki, rupa apa 400 dilo
{"entries": [{"customer_name": "tutul", "amount": 60, "type": "credit", "item": "cha", "confidence": 0.9}, {"customer_name": "rupa", "amount": 400, "type": "payment", "item": null, "confidence": 0.9}]}
Sentence: rina 2 ta saban r 1 packet biscuit
{"error": "no amount"}
"""

RETRY_PROMPT = """\
Your answer could not be used: {problem}
Reply again with ONLY the JSON object in the required format."""


_SENTENCE = "Sentence: "
_NORMALIZED = "\nSame sentence with numbers written as digits: "


def user_prompt(raw_text: str, normalized_text: str) -> str:
    prompt = f"{_SENTENCE}{raw_text}"
    if normalized_text != raw_text:
        prompt += f"{_NORMALIZED}{normalized_text}"
    return prompt


def sentence_from_user_prompt(prompt: str) -> str:
    """The original sentence back out of `user_prompt` (used by the rule-based demo parser)."""
    return prompt.removeprefix(_SENTENCE).split(_NORMALIZED, 1)[0]
