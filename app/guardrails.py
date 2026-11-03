"""Context and meaning checks applied after embedding every incoming question."""
import re
from decimal import Decimal

OUT_OF_SCOPE = "I'm here to help with store policies: refunds, returns, shipping, cancellations, and damaged items. Please ask a question about one of these topics."


def needs_history(text: str) -> bool:
    """References to earlier messages stay within that conversation context."""
    # A pronoun with its own explicit antecedent is not a chat-history reference.
    text = re.sub(r"\b((?:my|the|an?|our|your) (?:order|item|product|purchase|package))\s+(before|after|when|if|once)\s+it\b", r"\1 \2 the object", text, flags=re.I)
    text = re.sub(r"\b(a return|an item|a product)\s+(include|have|retain)\s+its\b", r"\1 \2 the", text, flags=re.I)
    text = re.sub(r"\b(is|would|will|could) it (?:be )?(possible|allowed|okay|ok|permitted)\b", r"\1 \2", text, flags=re.I)
    text = re.sub(r"\b((?:an?|the|my|our|your|any) (?:\w+\s+){0,2}(?:item|product|order|purchase|package|refund))\s+that\b", r"\1 which", text, flags=re.I)
    return bool(re.search(
        r"\b(it|its|that|this|these|those|them|they|same|previous|above|earlier|instead)\b"
        r"|^(and|also|what about|how about|why|yes|no|tell me more|explain more)\b",
        text, re.I,
    ))


def meaning_signature(text: str) -> tuple:
    """Embeddings can confuse opposites. Preserve explicit policy conditions."""
    lowered = text.casefold().replace("’", "'")
    lowered = re.sub(r"\b(?:(?:have|has|had|was|were|is|are) )?(?:not|never) (?:been )?(used|worn|opened)\b|\b(?:haven't|hasn't|hadn't|wasn't|weren't|isn't|aren't) (?:been )?(used|worn|opened)\b", lambda m: {"used": "unused", "worn": "unworn", "opened": "unopened"}[m[1] or m[2]], lowered)
    ones = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
    tens = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
    number_words = r"\b(?:" + "|".join(tens) + r")(?:[- ](?:" + "|".join(list(ones)[1:10]) + r"))?\b|\b(?:" + "|".join(ones) + r")\b"
    def as_number(match):
        return str(sum(ones.get(part, tens.get(part, 0)) for part in re.split(r"[- ]", match.group())))
    lowered = re.sub(number_words, as_number, lowered)
    patterns = {
        "before": r"\b(before|prior to)\b",
        "after": r"\b(after|already)\b|\bonce\b.{0,50}\b(shipped|dispatched)\b",
        "unused": r"\b(unused|unworn)\b",
        "used": r"\b(used|worn)\b",
        "unopened": r"\b(unopened|sealed)\b",
        "opened": r"\b(opened|unsealed)\b",
        "damaged": r"\b(damaged|broken|defective|faulty)\b",
        "personalized": r"\b(personalized|personalised|customized|customised|custom[ -]made)\b",
        "final-sale": r"\b(final.sale|clearance)\b",
        "international": r"\b(international|overseas|abroad)\b",
        "express": r"\b(express|expedited|overnight|next.day)\b",
        "return-shipping": r"\b(return shipping|return postage|return delivery|shipping (?:an? |the )?(?:item |product )?back)\b",
        "customer-damage": r"\b(?:i|we|you)\s+(?:accidentally\s+)?(?:damaged|broke)\b",
        "multiple-requests": r"\b(?:and|also|plus)\s+(?:can|could|do|does|will|would|are|is|what|how|when|where|get|receive|request)\b",
        "timing-start": r"\b(start|starts|begin|begins|commence|counting)\b",
        "order-change": r"\b(change|amend|edit|modify|update)\b.{0,30}\border\b|\border\b.{0,30}\b(change|amend|edit|modify|update)\b",
        "reporting": r"\b(report|reporting|notify|inform)\b|\bfile (?:a )?(?:claim|complaint)\b",
        "business-days": r"\b(business|working)\s+days?\b",
        "calendar-days": r"\bcalendar\s+days?\b",
        "less-than": r"\b(less than|under|fewer than)\b",
        "more-than": r"\b(more than|over|greater than)\b",
        "negation": r"\b(not|no|never|cannot|can't|don't|doesn't|isn't|aren't|won't|without)\b",
    }
    conditions = tuple(name for name, pattern in patterns.items() if re.search(pattern, lowered))
    quantities = tuple(
        (format(Decimal(number).normalize(), "f"), unit.rstrip("s"))
        for number, unit in re.findall(r"\b(\d+(?:\.\d+)?)\b\s*(?:(?:business|working|calendar)\s+)?(hours?|days?|weeks?|months?|years?)?", lowered)
    )
    return conditions, quantities


def reusable_request(text: str) -> bool:
    # Search still runs; requests containing identifiers or override instructions
    # cannot reuse or create shared answers. First-person policy questions can.
    return len(text) <= 1000 and not re.search(
        r"[\w.+-]+@[\w.-]+\.[a-z]+|https?://|\b\d{6,}\b"
        r"|\b(order|account|tracking)\s*(?:id|number|#|no\.)\s*[:#]?\s*\w+"
        r"|\b(ignore|override|pretend|system prompt|instructions|write code|translate)\b",
        text, re.I,
    )
