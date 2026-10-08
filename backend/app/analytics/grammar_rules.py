"""High-precision, rule-based detection of common learner errors.

The detector is intentionally conservative: every rule targets a pattern that is (almost)
always wrong, so it can run on any writing or speaking transcript without flooding learners
with false positives. It powers mock-mode evaluation and cross-checks AI-reported errors.

Each detection carries the exact original text and its character offsets, so the UI can
highlight it and the mistake tracker can store it verbatim.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.analytics.text import split_sentences, words


@dataclass
class DetectedError:
    category: str
    subcategory: str
    original: str
    corrected: str
    explanation: str
    severity: str
    start: int
    end: int
    rule_id: str
    context: str = ""
    highlight: bool = True


Fix = Callable[[re.Match], str]
Guard = Callable[[re.Match, str], bool]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern
    category: str
    subcategory: str
    severity: str
    explanation: str
    fix: Fix
    scope: str = "all"  # all | writing (not speaking) | academic (formal writing only)
    guard: Guard | None = None


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def match_case(source: str, replacement: str) -> str:
    if not source or not replacement:
        return replacement
    if source.isupper() and len(source) > 1:
        return replacement.upper()
    if source[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _swap_word(index: int, mapping: dict[str, str]) -> Fix:
    """Replace capture group `index` using `mapping`, keeping the rest of the match intact."""

    def fix(m: re.Match) -> str:
        whole = m.group(0)
        word = m.group(index)
        start = m.start(index) - m.start(0)
        end = m.end(index) - m.start(0)
        replacement = match_case(word, mapping.get(word.lower(), word))
        return whole[:start] + replacement + whole[end:]

    return fix


def _drop_group(index: int) -> Fix:
    def fix(m: re.Match) -> str:
        whole = m.group(0)
        start = m.start(index) - m.start(0)
        end = m.end(index) - m.start(0)
        result = (whole[:start] + whole[end:]).replace("  ", " ").strip()
        return match_case(whole, result)

    return fix


def _replace_with(template: str) -> Fix:
    def fix(m: re.Match) -> str:
        return match_case(m.group(0), m.expand(template))

    return fix


def _preceded_by(pattern: str) -> Guard:
    rx = re.compile(pattern + r"\s*$", re.IGNORECASE)

    def guard(m: re.Match, text: str) -> bool:
        return not rx.search(text[max(0, m.start() - 40) : m.start()])

    return guard


def _all_guards(*guards: Guard) -> Guard:
    def guard(m: re.Match, text: str) -> bool:
        return all(g(m, text) for g in guards)

    return guard


def _lowercase_group(index: int) -> Guard:
    def guard(m: re.Match, text: str) -> bool:
        value = m.group(index)
        return bool(value) and value[0].islower()

    return guard


def _article_guard(m: re.Match, text: str) -> bool:
    # "Section A is ..." - an uppercase A that follows a word is a label, not an article.
    if m.group(0)[0] == "A":
        before = text[: m.start()].rstrip()
        if before and before[-1].isalnum():
            return False
    return True


IRREGULAR_BASE = {
    "went": "go",
    "saw": "see",
    "ate": "eat",
    "took": "take",
    "made": "make",
    "came": "come",
    "got": "get",
    "gave": "give",
    "wrote": "write",
    "knew": "know",
    "thought": "think",
    "bought": "buy",
    "found": "find",
    "told": "tell",
    "became": "become",
    "began": "begin",
    "felt": "feel",
    "left": "leave",
    "brought": "bring",
    "kept": "keep",
    "said": "say",
    "spent": "spend",
    "paid": "pay",
    "chose": "choose",
    "grew": "grow",
    "ran": "run",
    "spoke": "speak",
    "understood": "understand",
    "had": "have",
    "has": "have",
    "goes": "go",
    "does": "do",
    "makes": "make",
    "gets": "get",
    "takes": "take",
    "gives": "give",
    "becomes": "become",
    "helps": "help",
    "helped": "help",
    "causes": "cause",
    "caused": "cause",
    "leads": "lead",
    "led": "lead",
    "needs": "need",
    "needed": "need",
    "wants": "want",
    "wanted": "want",
    "did": "do",
    "is": "be",
    "was": "be",
}

PLURALS = {
    "problem": "problems",
    "issue": "issues",
    "reason": "reasons",
    "thing": "things",
    "country": "countries",
    "student": "students",
    "factor": "factors",
    "idea": "ideas",
    "day": "days",
    "year": "years",
    "child": "children",
    "change": "changes",
    "benefit": "benefits",
    "advantage": "advantages",
    "disadvantage": "disadvantages",
    "solution": "solutions",
    "method": "methods",
    "measure": "measures",
    "job": "jobs",
    "city": "cities",
    "device": "devices",
    "skill": "skills",
    "person": "people",
    "way": "ways",
    "cause": "causes",
    "challenge": "challenges",
    "aspect": "aspects",
}

SINGULARS = {
    "people": "person",
    "students": "student",
    "children": "child",
    "countries": "country",
    "years": "year",
    "days": "day",
    "citizens": "citizen",
    "individuals": "individual",
}

GERUNDS = {
    "see": "seeing",
    "meet": "meeting",
    "hear": "hearing",
    "work": "working",
    "receive": "receiving",
    "visit": "visiting",
    "start": "starting",
    "discuss": "discussing",
    "speak": "speaking",
    "join": "joining",
}


def gerund(verb: str) -> str:
    v = verb.lower()
    if v in GERUNDS:
        return GERUNDS[v]
    if v.endswith("ie"):
        return v[:-2] + "ying"
    if v.endswith("e") and not v.endswith(("ee", "ye", "oe")):
        return v[:-1] + "ing"
    if len(v) <= 4 and len(v) >= 3 and v[-1] not in "aeiouwxy" and v[-2] in "aeiou" and v[-3] not in "aeiou":
        return v + v[-1] + "ing"
    return v + "ing"


MISSPELLINGS = {
    "recieve": "receive",
    "recieved": "received",
    "beleive": "believe",
    "beleived": "believed",
    "goverment": "government",
    "goverments": "governments",
    "enviroment": "environment",
    "enviromental": "environmental",
    "untill": "until",
    "wich": "which",
    "becuase": "because",
    "becasue": "because",
    "beacause": "because",
    "definately": "definitely",
    "seperate": "separate",
    "seperately": "separately",
    "occured": "occurred",
    "occurence": "occurrence",
    "accomodation": "accommodation",
    "adress": "address",
    "alot": "a lot",
    "arguement": "argument",
    "begining": "beginning",
    "beautifull": "beautiful",
    "buisness": "business",
    "bussiness": "business",
    "calender": "calendar",
    "commited": "committed",
    "comming": "coming",
    "concious": "conscious",
    "developement": "development",
    "dissapear": "disappear",
    "dissapoint": "disappoint",
    "embarass": "embarrass",
    "existance": "existence",
    "familar": "familiar",
    "finaly": "finally",
    "foriegn": "foreign",
    "freind": "friend",
    "freinds": "friends",
    "futher": "further",
    "happend": "happened",
    "immediatly": "immediately",
    "independant": "independent",
    "knowlege": "knowledge",
    "libary": "library",
    "maintainance": "maintenance",
    "neccessary": "necessary",
    "necesary": "necessary",
    "neccesary": "necessary",
    "noticable": "noticeable",
    "ocasion": "occasion",
    "oppurtunity": "opportunity",
    "oportunity": "opportunity",
    "oppertunity": "opportunity",
    "oportunities": "opportunities",
    "oppurtunities": "opportunities",
    "paralell": "parallel",
    "persue": "pursue",
    "posession": "possession",
    "prefered": "preferred",
    "privelege": "privilege",
    "probaly": "probably",
    "proffesional": "professional",
    "profesional": "professional",
    "publically": "publicly",
    "realy": "really",
    "recomend": "recommend",
    "recomended": "recommended",
    "refered": "referred",
    "relevent": "relevant",
    "responsability": "responsibility",
    "responsabilities": "responsibilities",
    "sucess": "success",
    "succes": "success",
    "sucessful": "successful",
    "succesful": "successful",
    "successfull": "successful",
    "suprise": "surprise",
    "tommorow": "tomorrow",
    "tomorow": "tomorrow",
    "truely": "truly",
    "wether": "whether",
    "writting": "writing",
    "writen": "written",
    "thier": "their",
    "teh": "the",
    "tecnology": "technology",
    "technolgy": "technology",
    "tehnology": "technology",
    "technlogy": "technology",
    "educaiton": "education",
    "studens": "students",
    "countrys": "countries",
    "citys": "cities",
    "familys": "families",
    "childs": "children",
    "economicaly": "economically",
    "basicly": "basically",
    "especialy": "especially",
    "generaly": "generally",
    "usualy": "usually",
    "actualy": "actually",
    "carefull": "careful",
    "helpfull": "helpful",
    "wonderfull": "wonderful",
    "polution": "pollution",
    "goverments'": "governments'",
    "comunity": "community",
    "comunication": "communication",
    "comittee": "committee",
    "challange": "challenge",
    "challanges": "challenges",
    "enviroments": "environments",
    "goals'": "goals'",
    "intresting": "interesting",
    "intrested": "interested",
    "beleif": "belief",
    "acheive": "achieve",
    "acheived": "achieved",
    "acheivement": "achievement",
    "agressive": "aggressive",
    "apparantly": "apparently",
    "assesment": "assessment",
    "benifit": "benefit",
    "benifits": "benefits",
    "benificial": "beneficial",
    "completly": "completely",
    "convienient": "convenient",
    "critisism": "criticism",
    "decison": "decision",
    "desicion": "decision",
    "diffrent": "different",
    "dificult": "difficult",
    "difficulity": "difficulty",
    "enviorment": "environment",
    "equiptment": "equipment",
    "experiance": "experience",
    "explaination": "explanation",
    "facilites": "facilities",
    "fourty": "forty",
    "goverment's": "government's",
    "grammer": "grammar",
    "harrass": "harass",
    "hieght": "height",
    "importent": "important",
    "improvment": "improvement",
    "infomation": "information",
    "langauge": "language",
    "lenght": "length",
    "managment": "management",
    "medecine": "medicine",
    "mispell": "misspell",
    "neighbour's": "neighbour's",
    "occassion": "occasion",
    "occuring": "occurring",
    "oppinion": "opinion",
    "opinon": "opinion",
    "peice": "piece",
    "percieve": "perceive",
    "perfomance": "performance",
    "permanant": "permanent",
    "posible": "possible",
    "possibilty": "possibility",
    "pratical": "practical",
    "prefrence": "preference",
    "problme": "problem",
    "realise's": "realise's",
    "reccomend": "recommend",
    "resourses": "resources",
    "restaraunt": "restaurant",
    "schedual": "schedule",
    "sentance": "sentence",
    "similiar": "similar",
    "sincerly": "sincerely",
    "specialy": "specially",
    "strenght": "strength",
    "succesfully": "successfully",
    "temperture": "temperature",
    "therefor": "therefore",
    "threshhold": "threshold",
    "throught": "through",
    "togather": "together",
    "tradditional": "traditional",
    "transfered": "transferred",
    "unfortunatly": "unfortunately",
    "unneccessary": "unnecessary",
    "untill.": "until.",
    "useing": "using",
    "vehical": "vehicle",
    "theirselves": "themselves",
    "theirself": "themselves",
    "hisself": "himself",
    "vehicals": "vehicles",
    "wierd": "weird",
    "whith": "with",
    "wheather": "whether",
}
MISSPELLINGS = {k: v for k, v in MISSPELLINGS.items() if k.isalpha() and k != v}

CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "can't": "cannot",
    "won't": "will not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "i'm": "I am",
    "they're": "they are",
    "we're": "we are",
    "you're": "you are",
    "i've": "I have",
    "we've": "we have",
    "they've": "they have",
    "shouldn't": "should not",
    "couldn't": "could not",
    "wouldn't": "would not",
    "didn't": "did not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "let's": "let us",
    "what's": "what is",
    "who's": "who is",
    "he's": "he is",
    "she's": "she is",
    "i'd": "I would",
    "we'd": "we would",
    "they'd": "they would",
    "i'll": "I will",
    "we'll": "we will",
    "they'll": "they will",
    "it'll": "it will",
}

INFORMAL = {
    "kids": "children",
    "stuff": "things",
    "gonna": "going to",
    "wanna": "want to",
    "gotta": "have to",
    "guys": "people",
    "okay": "acceptable",
    "ok": "acceptable",
    "awesome": "excellent",
    "kinda": "rather",
    "sorta": "somewhat",
    "totally": "completely",
}

_MODAL_GUARD = _preceded_by(
    r"\b(?:does|did|do|doesn't|didn't|don't|can|can't|cannot|could|couldn't|will|won't|would|wouldn't|should|shouldn't|"
    r"may|might|must|mustn't|to|let|make|made|help|helps)"
)
_OF_GROUP_GUARD = _preceded_by(r"\b(?:one|each|none|neither|either|every one|any|number) of(?: the| these| those| their| our| my| his| her)?")


def _third_person(verb: str) -> str:
    irregular = {"go": "goes", "do": "does", "have": "has", "say": "says", "pay": "pays", "stay": "stays", "buy": "buys", "enjoy": "enjoys"}
    if verb in irregular:
        return irregular[verb]
    if verb.endswith(("s", "sh", "ch", "x", "z")):
        return verb + "es"
    if verb.endswith("y") and verb[-2:-1] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"


def _vowel_article(m: re.Match) -> str:
    return match_case(m.group(1), "an") + m.group(0)[len(m.group(1)) :]


def _consonant_article(m: re.Match) -> str:
    return match_case(m.group(1), "a") + m.group(0)[len(m.group(1)) :]


def _insert_article(m: re.Match) -> str:
    verb, adjective, noun = m.group(1), m.group(2), m.group(3)
    article = "an" if adjective[0].lower() in "aeiou" else "a"
    return f"{verb} {article} {adjective} {noun}"


def _pluralise_after(m: re.Match) -> str:
    noun = m.group(m.lastindex or 1)
    whole = m.group(0)
    start = m.start(m.lastindex or 1) - m.start(0)
    return whole[:start] + match_case(noun, PLURALS.get(noun.lower(), noun + "s"))


def _every_singular(m: re.Match) -> str:
    return f"{m.group(1)} {SINGULARS.get(m.group(2).lower(), m.group(2))}"


def _base_after_aux(m: re.Match) -> str:
    return f"{m.group(1)} {match_case(m.group(2), IRREGULAR_BASE.get(m.group(2).lower(), m.group(2)))}"


def _modal_to(m: re.Match) -> str:
    return f"{m.group(1)} {m.group(2)}"


def _gerund_fix(prefix_group: int, verb_group: int) -> Fix:
    def fix(m: re.Match) -> str:
        return f"{m.group(prefix_group)} {gerund(m.group(verb_group))}"

    return fix


def _suggest_that(m: re.Match) -> str:
    pronoun = {"him": "he", "her": "she", "them": "they", "me": "I", "us": "we"}[m.group(2).lower()]
    return f"{m.group(1)} that {pronoun}"


def _collocation(verb_map: dict[str, str], tail: str) -> Fix:
    def fix(m: re.Match) -> str:
        verb = m.group(1)
        return match_case(verb, verb_map.get(verb.lower(), verb)) + tail

    return fix


_DO_TO_MAKE = {"do": "make", "does": "makes", "did": "made", "doing": "making", "done": "made"}
_MAKE_TO_DO = {"make": "do", "makes": "does", "made": "did", "making": "doing"}
_MAKE_TO_CARRY = {"make": "carry out", "makes": "carries out", "made": "carried out", "making": "carrying out"}
_RISE_TO_RAISE = {"rise": "raise", "rises": "raises", "rose": "raised", "rising": "raising"}

SVA = "Subject–verb agreement: plural subjects take plural verbs (are/were/have/do) and singular subjects take singular verbs (is/was/has/does)."

RULES: list[Rule] = [
    # ---------------------------------------------------------------- subject-verb agreement
    Rule(
        "sva_plural_subject",
        _rx(
            r"\b(people|children|they|we|men|women|students|governments|parents|teenagers|citizens|individuals|employees|companies|countries|cities|families)\s+(is|was|has|does|doesn't)\b"
        ),
        "grammar",
        "subject_verb_agreement",
        "medium",
        SVA,
        _swap_word(2, {"is": "are", "was": "were", "has": "have", "does": "do", "doesn't": "don't"}),
        guard=_OF_GROUP_GUARD,
    ),
    Rule(
        "sva_plural_subject_verb_s",
        _rx(
            r"\b(people|children|they|we|students|parents|teenagers|citizens|governments|many people|most people|some people)\s+(thinks|believes|says|wants|needs|likes|prefers|feels|knows|uses|spends|works|lives|goes|makes|gets|takes|agrees|argues|claims|seems|tends|wishes|enjoys|plays|watches|buys|studies)\b"
        ),
        "grammar",
        "subject_verb_agreement",
        "medium",
        SVA,
        lambda m: (
            f"{m.group(1)} "
            + match_case(m.group(2), {"goes": "go", "watches": "watch", "wishes": "wish", "studies": "study"}.get(m.group(2).lower(), m.group(2)[:-1]))
        ),
        guard=_OF_GROUP_GUARD,
    ),
    Rule(
        "sva_third_person",
        _rx(r"\b(he|she|it)\s+(have|do|are|don't)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "With he/she/it in the present simple, use has/does/is/doesn't.",
        _swap_word(2, {"have": "has", "do": "does", "are": "is", "don't": "doesn't"}),
        guard=_MODAL_GUARD,
    ),
    Rule(
        "sva_third_person_base",
        _rx(
            r"\b(he|she|it)\s+(play|make|give|take|help|cause|lead|need|want|seem|become|affect|provide|allow|create|mean|depend|include|require|offer|show|bring|keep|reduce|increase|improve)\b"
        ),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "In the present simple, he/she/it takes a verb ending in -s (it plays, she makes).",
        lambda m: (
            f"{m.group(1)} "
            + match_case(
                m.group(2), {"have": "has"}.get(m.group(2).lower(), m.group(2) + ("es" if m.group(2).lower().endswith(("s", "sh", "ch", "x")) else "s"))
            )
        ),
        guard=_MODAL_GUARD,
    ),
    Rule(
        "sva_third_person_everyday",
        _rx(
            r"\b(he|she)\s+(go|like|love|work|live|study|watch|eat|drink|think|know|say|get|come|feel|look|use|try|speak|read|write|"
            r"teach|learn|buy|pay|walk|enjoy|prefer|hate|believe|understand|remember|forget|plan|spend|visit|travel|cook|drive|"
            r"sleep|listen|call|ask|tell|wait|stay|wash|finish|watch|miss|teach|carry|worry|hurry)\b"
        ),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "In the present simple, he/she takes a verb ending in -s or -es (he jumps, she fixes, it rains).",
        lambda m: f"{m.group(1)} " + match_case(m.group(2), _third_person(m.group(2).lower())),
        guard=_all_guards(_MODAL_GUARD, _preceded_by(r"\b(?:and|nor|both \w+ and)")),
    ),
    Rule(
        "sva_i",
        _rx(r"\b(I)\s+(has|is|does|doesn't)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "With 'I', use have/am/do/don't.",
        _swap_word(2, {"has": "have", "is": "am", "does": "do", "doesn't": "don't"}),
        guard=_MODAL_GUARD,
    ),
    Rule(
        "sva_you_we_they",
        _rx(r"\b(you|we|they)\s+(has|is|was|does|doesn't)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        SVA,
        _swap_word(2, {"has": "have", "is": "are", "was": "were", "does": "do", "doesn't": "don't"}),
        guard=_MODAL_GUARD,
    ),
    Rule(
        "sva_there_are",
        _rx(r"\b(there)\s+(is|was)\s+(many|several|a number of|numerous|various|few|two|three|four|five|six|ten|\d+)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "Use 'there are/were' before a plural noun phrase.",
        _swap_word(2, {"is": "are", "was": "were"}),
    ),
    Rule(
        "sva_indefinite_pronoun",
        _rx(r"\b(everyone|everybody|nobody|somebody|someone|anyone|anybody|no one)\s+(are|have|were|do|don't)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "Indefinite pronouns such as everyone/nobody take a singular verb.",
        _swap_word(2, {"are": "is", "have": "has", "were": "was", "do": "does", "don't": "doesn't"}),
        guard=_MODAL_GUARD,
    ),
    Rule(
        "sva_number_of",
        _rx(r"\b(the number of \w+)\s+(are|have|were)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "'The number of + plural noun' is singular: the number of students IS rising.",
        _swap_word(2, {"are": "is", "have": "has", "were": "was"}),
    ),
    Rule(
        "sva_quantifier_plural",
        _rx(r"\b(a number of|many|several|both|various|numerous)\s+([a-z]+[^s\W]s)\s+(is|was|has)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        SVA,
        _swap_word(3, {"is": "are", "was": "were", "has": "have"}),
    ),
    Rule(
        "sva_one_of",
        _rx(r"\b(one of the \w+s)\s+(are|were|have)\b"),
        "grammar",
        "subject_verb_agreement",
        "medium",
        "'One of the + plural noun' takes a singular verb: one of the reasons IS...",
        _swap_word(2, {"are": "is", "were": "was", "have": "has"}),
    ),
    # ---------------------------------------------------------------- plurals & countability
    Rule(
        "det_this_plural",
        _rx(
            r"\b(this)\s+(problems|issues|reasons|things|countries|students|factors|ideas|days|years|people|children|changes|benefits|advantages|disadvantages|solutions|methods|measures|jobs|cities|devices|skills)\b"
        ),
        "grammar",
        "plural_forms",
        "medium",
        "Use 'these' (not 'this') before a plural noun.",
        _swap_word(1, {"this": "these"}),
    ),
    Rule(
        "det_these_singular",
        _rx(
            r"\b(these|those)\s+(problem|issue|reason|thing|country|student|factor|idea|day|year|child|change|benefit|advantage|disadvantage|solution|method|measure|job|city|device|skill|person)\b"
        ),
        "grammar",
        "plural_forms",
        "medium",
        "'These/those' must be followed by a plural noun.",
        _pluralise_after,
    ),
    Rule(
        "uncountable_plural",
        _rx(r"\b(informations|advices|knowledges|equipments|furnitures|homeworks|luggages|feedbacks|softwares)\b"),
        "grammar",
        "plural_forms",
        "medium",
        "This noun is uncountable in English, so it has no plural form.",
        lambda m: match_case(m.group(1), m.group(1)[:-1]),
    ),
    Rule(
        "uncountable_research",
        _rx(r"\b(the|many|some|several|these|those|various|such|numerous)\s+(researches)\b"),
        "grammar",
        "plural_forms",
        "medium",
        "'Research' is uncountable: use 'research' or 'studies'.",
        _swap_word(2, {"researches": "research"}),
    ),
    Rule(
        "many_uncountable",
        _rx(r"\b(many)\s+(information|advice|knowledge|equipment|furniture|research|evidence|homework|money|pollution|traffic|work|time)\b"),
        "grammar",
        "plural_forms",
        "medium",
        "Use 'much' or 'a great deal of' with uncountable nouns; 'many' is for countable plurals.",
        _swap_word(1, {"many": "much"}),
    ),
    Rule(
        "article_uncountable",
        _rx(
            r"\b(a|an)\s+(advice|information|evidence|equipment|furniture|news|feedback|luggage|research|homework)(?=\s+(?:about|on|that|from|in|for|to|which|is|was)\b|\s*[.,;!?]|$)"
        ),
        "grammar",
        "article_usage",
        "medium",
        "Uncountable nouns cannot take a/an. Use 'a piece of' or 'some'.",
        lambda m: ("some " if m.group(2).lower() in ("research", "homework") else "a piece of ") + m.group(2),
    ),
    Rule(
        "less_fewer",
        _rx(
            r"\b(less)\s+(people|students|cars|jobs|children|problems|opportunities|hours|countries|vehicles|employees|workers|accidents|crimes|trees|books|items|products)\b"
        ),
        "grammar",
        "plural_forms",
        "low",
        "Use 'fewer' with countable plural nouns and 'less' with uncountable nouns.",
        _swap_word(1, {"less": "fewer"}),
    ),
    Rule(
        "every_plural",
        _rx(r"\b(every)\s+(people|students|children|countries|years|days|citizens|individuals)\b"),
        "grammar",
        "plural_forms",
        "medium",
        "'Every' is followed by a singular noun.",
        _every_singular,
    ),
    Rule(
        "one_of_singular",
        _rx(
            r"\b(one of the (?:most )?(?:important|significant|main|biggest|best|major|greatest|common|serious) )(reason|problem|issue|factor|way|thing|cause|benefit|advantage|disadvantage|country|city|challenge|aspect)\b"
        ),
        "grammar",
        "plural_forms",
        "medium",
        "'One of the...' must be followed by a plural noun.",
        _pluralise_after,
    ),
    # ---------------------------------------------------------------- articles
    Rule(
        "a_before_vowel",
        _rx(r"\b(a)\s+(?=[aeio])(?!one\b|once\b|eu|ewe|uni|use|usu|uti|eur)([a-z][\w-]*)"),
        "grammar",
        "article_usage",
        "low",
        "Use 'an' before a word that begins with a vowel sound.",
        _vowel_article,
        guard=_all_guards(_lowercase_group(2), _article_guard),
    ),
    Rule(
        "a_before_u_vowel",
        _rx(r"\b(a)\s+(un(?:[hkeflprstwcdbmnu]|a(?!n)|im|in)\w*|umbrella\w*|upp\w*|ugl\w*|ult\w*|urg\w*|urb\w*|upset\w*|upward\w*)\b"),
        "grammar",
        "article_usage",
        "low",
        "Use 'an' before a word that begins with a vowel sound.",
        _vowel_article,
        guard=_all_guards(_lowercase_group(2), _article_guard),
    ),
    Rule(
        "a_before_silent_h",
        _rx(r"\b(a)\s+(hour|hours|honest|honour|honor|heir|honourable|honorable)\b"),
        "grammar",
        "article_usage",
        "low",
        "Words such as 'hour' and 'honest' start with a vowel sound, so they take 'an'.",
        _vowel_article,
        guard=_article_guard,
    ),
    Rule(
        "an_before_consonant",
        _rx(r"\b(an)\s+(?=[bcdfgjklmnpqrstvwyz])([a-z][\w-]*)"),
        "grammar",
        "article_usage",
        "low",
        "Use 'a' before a word that begins with a consonant sound.",
        _consonant_article,
        guard=_lowercase_group(2),
    ),
    Rule(
        "an_before_h",
        _rx(r"\b(an)\s+(h(?!our|onest|onou?r|eir)[a-z][\w-]*)"),
        "grammar",
        "article_usage",
        "low",
        "Use 'a' before a word that begins with a pronounced /h/ sound (a huge, a house).",
        _consonant_article,
        guard=_lowercase_group(2),
    ),
    Rule(
        "an_before_you_sound",
        _rx(r"\b(an)\s+(uni(?!m|n)\w*|use\w*|usu\w*|uti\w*|eu\w*|one\b|once\b)"),
        "grammar",
        "article_usage",
        "low",
        "Words such as 'university', 'useful' and 'European' start with a /j/ sound, so they take 'a'.",
        _consonant_article,
        guard=_lowercase_group(2),
    ),
    Rule(
        "missing_article",
        _rx(
            r"\b(is|was|be|becomes|become|became)\s+(serious|big|major|significant|huge|common|important|difficult|great|growing|key|good|bad|crucial|effective|useful|positive|negative|essential|excellent)\s+(problem|issue|idea|way|reason|example|solution|challenge|factor|concern|threat|step|decision|opportunity|trend|source|tool|method)\b"
        ),
        "grammar",
        "article_usage",
        "medium",
        "A singular countable noun needs an article: 'a serious problem', 'an important factor'.",
        _insert_article,
    ),
    Rule(
        "the_nature",
        _rx(r"\b(protect|destroy|love|enjoy|preserve|harm|damage|respect|save)\s+the\s+nature\b"),
        "grammar",
        "article_usage",
        "low",
        "'Nature' in the general sense takes no article.",
        lambda m: f"{m.group(1)} nature",
    ),
    Rule(
        "most_of_people",
        _rx(r"\b(most of)\s+(people|students|children|countries|adults|teenagers|parents|families|cities|governments|companies)\b"),
        "grammar",
        "article_usage",
        "medium",
        "Use 'most + plural noun' for general statements, or 'most of the + noun' for a specific group.",
        lambda m: match_case(m.group(1), "most") + f" {m.group(2)}",
    ),
    Rule(
        "in_nowadays",
        _rx(r"\b(in\s+(?:the\s+)?nowadays|now\s+a\s+days)\b"),
        "grammar",
        "preposition",
        "low",
        "'Nowadays' is an adverb on its own: write 'nowadays' (no 'in').",
        lambda m: match_case(m.group(1), "nowadays"),
    ),
    # ---------------------------------------------------------------- prepositions
    Rule(
        "discuss_about",
        _rx(r"\b(discuss(?:es|ed|ing)?)\s+(about)\b"),
        "grammar",
        "preposition",
        "medium",
        "'Discuss' is followed directly by its object: discuss a topic (not discuss about).",
        _drop_group(2),
    ),
    Rule(
        "emphasise_on",
        _rx(r"\b(emphasi[sz](?:e|es|ed|ing))\s+(on)\b"),
        "grammar",
        "preposition",
        "medium",
        "'Emphasise' takes a direct object (emphasise the need). Use 'emphasis on' only with the noun.",
        _drop_group(2),
    ),
    Rule(
        "mention_about",
        _rx(r"\b(mention(?:s|ed|ing)?)\s+(about)\b"),
        "grammar",
        "preposition",
        "medium",
        "'Mention' is followed directly by its object.",
        _drop_group(2),
    ),
    Rule(
        "explain_me",
        _rx(r"\b(explain(?:s|ed|ing)?)\s+(me|him|her|us|them)\b"),
        "grammar",
        "preposition",
        "medium",
        "Say 'explain something TO someone', not 'explain someone'.",
        lambda m: f"{m.group(1)} to {m.group(2)}",
    ),
    Rule(
        "depend_of",
        _rx(r"\b(depend|depends|depended|depending|dependent)\s+(of)\b"),
        "grammar",
        "preposition",
        "medium",
        "The correct preposition is 'depend on'.",
        _swap_word(2, {"of": "on"}),
    ),
    Rule(
        "interested_in",
        _rx(r"\b(interested)\s+(on|for|about)\b"),
        "grammar",
        "preposition",
        "medium",
        "We are interested IN something.",
        _swap_word(2, {"on": "in", "for": "in", "about": "in"}),
    ),
    Rule("married_to", _rx(r"\b(married)\s+(with)\b"), "grammar", "preposition", "low", "We say 'married to someone'.", _swap_word(2, {"with": "to"})),
    Rule(
        "arrive_to",
        _rx(r"\b(arrive|arrives|arrived|arriving)\s+(to)\b"),
        "grammar",
        "preposition",
        "medium",
        "Use 'arrive in' (cities, countries) or 'arrive at' (buildings, stations) - never 'arrive to'.",
        _swap_word(2, {"to": "in"}),
    ),
    Rule(
        "on_the_other_hand",
        _rx(r"\b(in)\s+(the\s+)?other\s+hand\b"),
        "grammar",
        "preposition",
        "medium",
        "The linking phrase is 'on the other hand'.",
        lambda m: match_case(m.group(0), "on the other hand"),
    ),
    Rule(
        "from_point_of_view",
        _rx(r"\b(in)\s+(my|our|their|his|her)\s+point of view\b"),
        "grammar",
        "preposition",
        "low",
        "We say 'from my point of view' (or 'in my view').",
        lambda m: match_case(m.group(1), "from") + f" {m.group(2)} point of view",
    ),
    Rule(
        "in_my_opinion",
        _rx(r"\b(on)\s+(my|our)\s+(opinion|view)\b"),
        "grammar",
        "preposition",
        "low",
        "We say 'in my opinion' / 'in my view'.",
        lambda m: match_case(m.group(1), "in") + f" {m.group(2)} {m.group(3)}",
    ),
    Rule(
        "focus_on",
        _rx(r"\b(focus|focuses|focused|focusing)\s+(in)\b(?!\s+on)"),
        "grammar",
        "preposition",
        "medium",
        "We focus ON something.",
        _swap_word(2, {"in": "on"}),
    ),
    Rule(
        "responsible_for",
        _rx(r"\b(responsible)\s+(of)\b"),
        "grammar",
        "preposition",
        "medium",
        "We are responsible FOR something.",
        _swap_word(2, {"of": "for"}),
    ),
    Rule(
        "contribute_to",
        _rx(r"\b(contribute|contributes|contributed|contributing)\s+(for)\b"),
        "grammar",
        "preposition",
        "medium",
        "We contribute TO something.",
        _swap_word(2, {"for": "to"}),
    ),
    Rule(
        "invest_in",
        _rx(r"\b(invest|invests|invested|investing)\s+(on)\b"),
        "grammar",
        "preposition",
        "medium",
        "We invest IN something.",
        _swap_word(2, {"on": "in"}),
    ),
    Rule(
        "succeed_in",
        _rx(r"\b(succeed|succeeds|succeeded)\s+(to)\b"),
        "grammar",
        "preposition",
        "medium",
        "Use 'succeed in + -ing' (e.g. succeed in finding).",
        _swap_word(2, {"to": "in"}),
    ),
    Rule("aware_of", _rx(r"\b(aware)\s+(about)\b"), "grammar", "preposition", "medium", "We are aware OF something.", _swap_word(2, {"about": "of"})),
    Rule("capable_of", _rx(r"\b(capable)\s+(to)\b"), "grammar", "preposition", "medium", "Use 'capable of + -ing'.", _swap_word(2, {"to": "of"})),
    Rule(
        "impact_on",
        _rx(r"\b(impacts?|effects?|influences?)\s+(to)\b(?=\s+(?:the|a|an|our|their|people|society|children|students|health|environment)\b)"),
        "grammar",
        "preposition",
        "medium",
        "We say an impact/effect/influence ON something.",
        _swap_word(2, {"to": "on"}),
    ),
    Rule(
        "on_days",
        _rx(r"\b(in)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b"),
        "grammar",
        "preposition",
        "low",
        "Use 'on' with days of the week.",
        _swap_word(1, {"in": "on"}),
    ),
    Rule(
        "in_the_morning",
        _rx(r"\b(at)\s+(morning|afternoon|evening)\b"),
        "grammar",
        "preposition",
        "low",
        "We say 'in the morning/afternoon/evening' (but 'at night').",
        lambda m: match_case(m.group(1), "in") + f" the {m.group(2)}",
    ),
    Rule(
        "since_for",
        _rx(r"\b(since)\s+((?:\d+|two|three|four|five|six|seven|eight|nine|ten|several|many|a few)\s+(?:years|months|weeks|days|decades|hours))\b"),
        "grammar",
        "preposition",
        "medium",
        "Use 'for' with a period of time and 'since' with a starting point (since 2015).",
        lambda m: match_case(m.group(1), "for") + f" {m.group(2)}",
    ),
    Rule(
        "despite_of",
        _rx(r"\b(despite)\s+(of)\b"),
        "grammar",
        "preposition",
        "medium",
        "'Despite' is never followed by 'of' (but 'in spite of' is correct).",
        _drop_group(2),
    ),
    Rule(
        "affect_on",
        _rx(r"\b(affect|affects|affected|affecting)\s+(on)\b"),
        "grammar",
        "preposition",
        "medium",
        "'Affect' is a transitive verb: affect something (not affect on).",
        _drop_group(2),
        guard=_preceded_by(
            r"\b(?:a|an|the|positive|negative|significant|huge|big|great|major|serious|harmful|beneficial|adverse|profound|direct|lasting|strong|little|no)"
        ),
    ),
    Rule(
        "misc_prepositions",
        _rx(r"\b(comply to|consist on|similar with|different with|proud on|afraid from|listen music|reply me|wait (?:me|him|her|them|us))\b"),
        "grammar",
        "preposition",
        "medium",
        "This verb/adjective needs a different preposition.",
        lambda m: match_case(
            m.group(1),
            {
                "comply to": "comply with",
                "consist on": "consist of",
                "similar with": "similar to",
                "different with": "different from",
                "proud on": "proud of",
                "afraid from": "afraid of",
                "listen music": "listen to music",
                "reply me": "reply to me",
            }.get(m.group(1).lower(), re.sub(r"^wait ", "wait for ", m.group(1), flags=re.IGNORECASE)),
        ),
    ),
    Rule(
        "reach_to",
        _rx(r"\b(reach(?:es|ed|ing)?)\s+(to)\s+(?=(?:the|a|an|their|our|its)\b)"),
        "grammar",
        "preposition",
        "low",
        "'Reach' takes a direct object: reach a conclusion / reach the city.",
        lambda m: f"{m.group(1)} ",
    ),
    # ---------------------------------------------------------------- verb forms, tense, modals
    Rule(
        "am_agree",
        _rx(r"\b(am|is|are|was|were)\s+(agree|disagree)\b"),
        "grammar",
        "verb_tense",
        "medium",
        "'Agree' is a verb, so it does not need 'am/is/are': I agree / I disagree.",
        lambda m: m.group(2),
    ),
    Rule(
        "aux_past",
        _rx(
            r"\b(did|didn't|did not|does|doesn't|does not|do|don't|do not)\s+(went|saw|ate|took|made|came|got|gave|wrote|knew|thought|bought|found|told|became|began|felt|left|brought|kept|said|spent|paid|chose|grew|ran|spoke|understood|had|has|goes|makes|gets|takes)\b"
        ),
        "grammar",
        "verb_tense",
        "medium",
        "After do/does/did, use the base form of the verb.",
        _base_after_aux,
    ),
    Rule(
        "modal_to",
        _rx(r"\b(can|could|should|must|might|will|would|shall)\s+to\s+([a-z]+)\b"),
        "grammar",
        "modal_verbs",
        "medium",
        "Modal verbs are followed by the base verb without 'to'.",
        _modal_to,
        guard=_preceded_by(r"\b(?:the|a|their|his|her|political|strong|own|free)"),
    ),
    Rule(
        "modal_inflected",
        _rx(
            r"\b(can|could|should|must|might|will|would|shall)\s+(goes|makes|has|does|went|made|had|did|gets|got|takes|took|gives|gave|becomes|became|helps|helped|causes|caused|leads|led|needs|needed|wants|wanted)\b"
        ),
        "grammar",
        "modal_verbs",
        "medium",
        "Modal verbs are followed by the base form of the verb.",
        _base_after_aux,
        guard=lambda m, text: not (m.group(1) == "Will" and m.start() > 0 and text[: m.start()].rstrip()[-1:].isalnum()),
    ),
    Rule(
        "double_comparative",
        _rx(
            r"\b(more)\s+(better|worse|easier|bigger|smaller|cheaper|faster|harder|higher|lower|larger|stronger|healthier|happier|richer|poorer|older|younger|safer|greater|longer|shorter)\b"
        ),
        "grammar",
        "comparatives",
        "medium",
        "Do not use 'more' with a comparative that already ends in -er (or with better/worse).",
        lambda m: m.group(2),
    ),
    Rule(
        "double_superlative",
        _rx(r"\b(most)\s+(best|worst|biggest|easiest|largest|highest|lowest|smallest|greatest|strongest|healthiest|happiest|richest|poorest)\b"),
        "grammar",
        "comparatives",
        "medium",
        "Do not use 'most' with a superlative that already ends in -est (or with best/worst).",
        lambda m: m.group(2),
    ),
    Rule(
        "look_forward_ing",
        _rx(r"\b(look(?:s|ed|ing)?\s+forward\s+to)\s+(see|meet|hear|work|receive|visit|start|discuss|speak|join)\b"),
        "grammar",
        "verb_tense",
        "medium",
        "In 'look forward to', 'to' is a preposition, so use the -ing form.",
        _gerund_fix(1, 2),
    ),
    Rule(
        "if_will",
        _rx(r"\b(if\s+(?:i|you|we|they|he|she|it|people|governments?|students?|someone|everyone))\s+(will)\s+"),
        "grammar",
        "conditionals",
        "medium",
        "In first-conditional sentences, use the present simple after 'if' (not 'will').",
        lambda m: f"{m.group(1)} ",
    ),
    Rule(
        "suggest_object_to",
        _rx(r"\b(suggest|suggests|suggested|recommend|recommends|recommended)\s+(him|her|them|me|us)\s+to\b"),
        "grammar",
        "sentence_structure",
        "medium",
        "Use 'suggest/recommend that someone (should) do', not 'suggest someone to do'.",
        _suggest_that,
    ),
    Rule(
        "let_make_to",
        _rx(r"\b(let|lets|make|makes|made)\s+(me|him|her|them|us|people|students|children)\s+to\s+([a-z]+)\b"),
        "grammar",
        "verb_tense",
        "medium",
        "After let/make + object, use the base verb without 'to'.",
        lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}",
    ),
    Rule(
        "verb_gerund",
        _rx(r"\b(enjoy|enjoys|enjoyed|avoid|avoids|avoided|finish|finished|mind|suggest|suggests)\s+to\s+([a-z]+)\b"),
        "grammar",
        "verb_tense",
        "medium",
        "This verb is followed by the -ing form (e.g. enjoy reading, avoid making).",
        _gerund_fix(1, 2),
        guard=lambda m, text: m.group(2).lower() not in ("be", "have", "the", "a", "an", "my", "their"),
    ),
    # ---------------------------------------------------------------- collocations & word choice
    Rule(
        "make_research",
        _rx(r"\b(make|makes|made|making)\s+(?:a\s+)?research(?:es)?\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'do' or 'carry out' research, not 'make' it.",
        _collocation(_MAKE_TO_CARRY, " research"),
    ),
    Rule(
        "do_mistake",
        _rx(r"\b(do|does|did|doing|done)\s+(a\s+|many\s+|some\s+|several\s+|lots of\s+|a lot of\s+)?(mistakes?)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "The collocation is 'make a mistake'.",
        lambda m: match_case(m.group(1), _DO_TO_MAKE[m.group(1).lower()]) + " " + (m.group(2) or "") + m.group(3),
    ),
    Rule(
        "make_homework",
        _rx(r"\b(make|makes|made|making)\s+((?:my |your |their |his |her |the )?homework)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'do' homework.",
        lambda m: match_case(m.group(1), _MAKE_TO_DO[m.group(1).lower()]) + f" {m.group(2)}",
    ),
    Rule(
        "do_decision",
        _rx(r"\b(do|does|did|doing)\s+(a\s+)?(decisions?)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "The collocation is 'make a decision'.",
        lambda m: match_case(m.group(1), _DO_TO_MAKE[m.group(1).lower()]) + " " + (m.group(2) or "") + m.group(3),
    ),
    Rule(
        "do_progress",
        _rx(r"\b(do|does|did|doing)\s+progress\b"),
        "vocabulary",
        "collocation",
        "medium",
        "The collocation is 'make progress'.",
        _collocation(_DO_TO_MAKE, " progress"),
    ),
    Rule(
        "make_crime",
        _rx(r"\b(make|makes|made|making)\s+(a\s+)?(crimes?)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'commit' a crime.",
        lambda m: (
            match_case(m.group(1), {"make": "commit", "makes": "commits", "made": "committed", "making": "committing"}[m.group(1).lower()])
            + " "
            + (m.group(2) or "")
            + m.group(3)
        ),
    ),
    Rule(
        "say_lie",
        _rx(r"\b(say|says|said|saying)\s+(a\s+)?(lies?)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'tell' lies.",
        lambda m: (
            match_case(m.group(1), {"say": "tell", "says": "tells", "said": "told", "saying": "telling"}[m.group(1).lower()])
            + " "
            + (m.group(2) or "")
            + m.group(3)
        ),
    ),
    Rule(
        "rise_raise",
        _rx(r"\b(rise|rises|rose|rising)\s+(awareness|a question|questions|money|funds|children|prices|taxes|salaries|standards)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "'Rise' has no object; to increase something, use 'raise' (raise awareness, raise taxes).",
        lambda m: match_case(m.group(1), _RISE_TO_RAISE[m.group(1).lower()]) + f" {m.group(2)}",
    ),
    Rule(
        "make_attention",
        _rx(r"\b(make|makes|made|making)\s+attention\b"),
        "vocabulary",
        "collocation",
        "medium",
        "The collocation is 'pay attention'.",
        _collocation({"make": "pay", "makes": "pays", "made": "paid", "making": "paying"}, " attention"),
    ),
    Rule(
        "earn_knowledge",
        _rx(r"\b(earn|earns|earned|earning)\s+knowledge\b"),
        "vocabulary",
        "collocation",
        "low",
        "We 'gain' or 'acquire' knowledge (we 'earn' money).",
        _collocation({"earn": "gain", "earns": "gains", "earned": "gained", "earning": "gaining"}, " knowledge"),
    ),
    Rule(
        "do_effort",
        _rx(r"\b(do|does|did|doing)\s+(?:an\s+)?efforts?\b"),
        "vocabulary",
        "collocation",
        "medium",
        "The collocation is 'make an effort'.",
        _collocation(_DO_TO_MAKE, " an effort"),
    ),
    Rule(
        "take_an_advantage",
        _rx(r"\b(take|takes|took|taking)\s+an\s+advantage\b"),
        "vocabulary",
        "collocation",
        "low",
        "The expression is 'take advantage of' (no article).",
        lambda m: f"{m.group(1)} advantage",
    ),
    Rule(
        "big_amount",
        _rx(r"\b(big)\s+(amount|number|quantity|proportion|percentage)\b"),
        "vocabulary",
        "collocation",
        "low",
        "Natural collocations are 'a large amount/number/proportion'.",
        lambda m: match_case(m.group(1), "large") + f" {m.group(2)}",
    ),
    Rule(
        "strong_rain",
        _rx(r"\b(strong)\s+(rain|rainfall|traffic)\b"),
        "vocabulary",
        "collocation",
        "low",
        "We say 'heavy rain' and 'heavy traffic'.",
        lambda m: match_case(m.group(1), "heavy") + f" {m.group(2)}",
    ),
    Rule(
        "make_damage",
        _rx(r"\b(make|makes|made|making)\s+(?:a\s+)?damage\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'cause' or 'do' damage.",
        _collocation({"make": "cause", "makes": "causes", "made": "caused", "making": "causing"}, " damage"),
    ),
    Rule(
        "make_sport",
        _rx(r"\b(make|makes|made|making)\s+(sports?|exercise)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'do' sport and 'do/take' exercise.",
        lambda m: match_case(m.group(1), _MAKE_TO_DO[m.group(1).lower()]) + f" {m.group(2)}",
    ),
    Rule(
        "make_exam",
        _rx(r"\b(make|makes|made|making)\s+(an?\s+)?(exams?|tests?)\b"),
        "vocabulary",
        "collocation",
        "medium",
        "We 'take' (or 'sit') an exam.",
        lambda m: (
            match_case(m.group(1), {"make": "take", "makes": "takes", "made": "took", "making": "taking"}[m.group(1).lower()])
            + " "
            + (m.group(2) or "")
            + m.group(3)
        ),
    ),
    Rule(
        "learn_teach",
        _rx(r"\b(learn|learns|learned|learnt|learning)\s+(me|him|her|us|children|students|people)\s+(how|to|about)\b"),
        "vocabulary",
        "word_choice",
        "medium",
        "To pass knowledge to someone is 'teach'; 'learn' means to receive knowledge.",
        lambda m: (
            match_case(m.group(1), {"learn": "teach", "learns": "teaches", "learned": "taught", "learnt": "taught", "learning": "teaching"}[m.group(1).lower()])
            + f" {m.group(2)} {m.group(3)}"
        ),
    ),
    Rule(
        "open_light",
        _rx(r"\b(open|close)\s+the\s+(lights?|tv|television|radio)\b"),
        "vocabulary",
        "collocation",
        "low",
        "We 'turn on/off' (or 'switch on/off') lights and devices.",
        lambda m: match_case(m.group(1), "turn on" if m.group(1).lower() == "open" else "turn off") + f" the {m.group(2)}",
    ),
    Rule(
        "make_photo",
        _rx(r"\b(make|makes|made|making)\s+(a\s+)?(photos?|pictures?)\b"),
        "vocabulary",
        "collocation",
        "low",
        "We 'take' photos.",
        lambda m: (
            match_case(m.group(1), {"make": "take", "makes": "takes", "made": "took", "making": "taking"}[m.group(1).lower()])
            + " "
            + (m.group(2) or "")
            + m.group(3)
        ),
    ),
    Rule(
        "economical_growth",
        _rx(r"\b(economical)\s+(growth|development|crisis|problems?|policy|policies|situation|reasons?|benefits?|issues?|system|power|inequality|stability)\b"),
        "vocabulary",
        "word_formation",
        "medium",
        "'Economic' relates to the economy; 'economical' means saving money.",
        lambda m: match_case(m.group(1), "economic") + f" {m.group(2)}",
    ),
    Rule(
        "affect_noun",
        _rx(
            r"\b(a|an|the|positive|negative|significant|huge|big|great|major|serious|harmful|beneficial|adverse|profound|direct|lasting|strong|little|no)\s+(affect)\b"
        ),
        "vocabulary",
        "word_formation",
        "medium",
        "'Effect' is the noun (a positive effect); 'affect' is the verb.",
        lambda m: (m.group(1) + " " + match_case(m.group(2), "effect")) if m.group(1).lower() not in ("a",) else "an effect",
    ),
    Rule(
        "effect_verb",
        _rx(
            r"\b(will|can|could|might|would|does|do|did|not|negatively|positively|directly|seriously|greatly)\s+(effect)\b(?!\s+(?:change|changes|a change|real change|reform))"
        ),
        "vocabulary",
        "word_formation",
        "medium",
        "'Affect' is the verb (it affects health); 'effect' is usually the noun.",
        lambda m: f"{m.group(1)} " + match_case(m.group(2), "affect"),
    ),
    Rule(
        "there_their",
        _rx(r"\b(there)\s+(own|children|parents|families|jobs|homes|lives|country|house|future|health|careers?|friends|money|skills)\b"),
        "spelling",
        "spelling",
        "medium",
        "Use 'their' (possessive) - 'there' refers to a place or begins 'there is/are'.",
        lambda m: match_case(m.group(1), "their") + f" {m.group(2)}",
    ),
    Rule(
        "their_there",
        _rx(r"\b(their)\s+(is|are|was|were)\b"),
        "spelling",
        "spelling",
        "medium",
        "Use 'there is/are' - 'their' is a possessive.",
        lambda m: match_case(m.group(1), "there") + f" {m.group(2)}",
    ),
    Rule(
        "then_than",
        _rx(
            r"\b(more|less|better|worse|higher|lower|bigger|smaller|greater|rather|other|fewer|faster|older|younger|cheaper|easier|harder|larger|longer|shorter|stronger|weaker)\s+(then)\b"
        ),
        "spelling",
        "spelling",
        "medium",
        "Use 'than' for comparisons; 'then' refers to time.",
        lambda m: f"{m.group(1)} " + match_case(m.group(2), "than"),
    ),
    Rule(
        "advice_advise",
        _rx(r"\b(i|we|they|you|would|will|should|strongly|must)\s+(advice)\b"),
        "vocabulary",
        "word_formation",
        "medium",
        "'Advise' is the verb; 'advice' is the noun.",
        lambda m: f"{m.group(1)} " + match_case(m.group(2), "advise"),
    ),
    Rule(
        "loose_lose",
        _rx(r"\b(loose|looses|loosing)\s+(weight|money|time|their|his|her|my|your|our|jobs?|interest|control|confidence|touch|sight)\b"),
        "spelling",
        "spelling",
        "medium",
        "'Lose' means to stop having something; 'loose' means not tight.",
        lambda m: match_case(m.group(1), {"loose": "lose", "looses": "loses", "loosing": "losing"}[m.group(1).lower()]) + f" {m.group(2)}",
    ),
    Rule(
        "according_to_me",
        _rx(r"\b(according to me)\b"),
        "vocabulary",
        "word_choice",
        "low",
        "'According to' introduces someone else's view. For your own view use 'In my opinion'.",
        lambda m: match_case(m.group(1), "in my opinion"),
    ),
    Rule(
        "can_not",
        _rx(r"\b(can not)\b(?!\s+only)"),
        "spelling",
        "spelling",
        "low",
        "'Cannot' is normally written as one word.",
        lambda m: match_case(m.group(1), "cannot"),
    ),
    Rule(
        "redundant_back",
        _rx(r"\b(return back|repeat again|revert back)\b"),
        "vocabulary",
        "word_choice",
        "low",
        "This is redundant: 'return' already means 'go back'.",
        lambda m: match_case(m.group(1), m.group(1).split()[0]),
    ),
    Rule(
        "very_absolute",
        _rx(r"\b(very|so)\s+(unique|essential|crucial|vital|perfect|fundamental)\b"),
        "vocabulary",
        "word_choice",
        "low",
        "Adjectives such as 'unique' or 'essential' are absolute and are not normally intensified with 'very'.",
        lambda m: m.group(2),
    ),
    Rule(
        "for_example_like",
        _rx(r"\b(for example like|for instance like)\b"),
        "vocabulary",
        "word_choice",
        "low",
        "Use either 'for example' or 'such as' - not both.",
        lambda m: match_case(m.group(1), "for example"),
    ),
    # ---------------------------------------------------------------- sentence structure & punctuation
    Rule(
        "comma_splice_however",
        _rx(r"\b(\w+),\s+however\s+([a-z]\w*)"),
        "grammar",
        "punctuation",
        "medium",
        "'However' cannot join two clauses with a comma. Use a semicolon or a full stop before it and a comma after it.",
        lambda m: f"{m.group(1)}; however, {m.group(2)}",
        scope="writing",
    ),
    Rule(
        "although_but",
        _rx(r"\b(although|though|even though)\b([^.!?;]{3,120}?),\s*(but)\b\s*"),
        "grammar",
        "sentence_structure",
        "medium",
        "Do not use 'although' and 'but' in the same sentence - choose one.",
        lambda m: f"{m.group(1)}{m.group(2)}, ",
    ),
    Rule(
        "because_of_clause",
        _rx(
            r"\b(because of)\s+(they|he|she|it|we|people|the government|governments|children|students)\s+(is|are|was|were|have|has|can|will|do|does|did|cannot|can't|don't)\b"
        ),
        "grammar",
        "sentence_structure",
        "medium",
        "'Because of' is followed by a noun; use 'because' before a clause (subject + verb).",
        lambda m: match_case(m.group(1), "because") + f" {m.group(2)} {m.group(3)}",
    ),
    Rule(
        "reason_is_because",
        _rx(r"\b(the reason (?:is|was) because)\b"),
        "grammar",
        "sentence_structure",
        "low",
        "Say 'the reason is that...' (or simply 'because...').",
        lambda m: match_case(m.group(1), m.group(1).lower().replace("because", "that")),
    ),
    Rule(
        "space_before_punct",
        re.compile(r"(\w)[ \t]+([,;:!?])(?=\s|$)"),
        "grammar",
        "punctuation",
        "low",
        "Do not put a space before a punctuation mark.",
        lambda m: f"{m.group(1)}{m.group(2)}",
        scope="writing",
    ),
    Rule(
        "missing_space_after_comma",
        re.compile(r"\b([A-Za-z]+),([A-Za-z]+)\b"),
        "grammar",
        "punctuation",
        "low",
        "Put a space after a comma.",
        lambda m: f"{m.group(1)}, {m.group(2)}",
        scope="writing",
    ),
    Rule(
        "lowercase_i",
        re.compile(r"(?<![\w'’(\-])(i)(?=\s+[a-z]|'m\b|’m\b|'ve\b|'ll\b|'d\b)"),
        "spelling",
        "capitalization",
        "low",
        "The pronoun 'I' is always written with a capital letter.",
        lambda m: "I",
        scope="writing",
    ),
    Rule(
        "repeated_word",
        _rx(r"\b(?!(?:that|had|is|bye|no|ha|very|so)\b)([a-z]+)\s+\1\b"),
        "spelling",
        "spelling",
        "low",
        "This word is repeated by mistake.",
        lambda m: m.group(1),
        scope="writing",
    ),
]

_MISSPELLING_RX = re.compile(r"\b(" + "|".join(sorted(map(re.escape, MISSPELLINGS), key=len, reverse=True)) + r")\b", re.IGNORECASE)
_CONTRACTION_RX = re.compile(
    r"(?<![\w'’])(" + "|".join(re.escape(c).replace("'", "['’]") for c in sorted(CONTRACTIONS, key=len, reverse=True)) + r")(?![\w'’])",
    re.IGNORECASE,
)
_INFORMAL_RX = re.compile(r"\b(" + "|".join(INFORMAL) + r"|tons of|loads of|a bunch of)\b", re.IGNORECASE)


def _special_detections(text: str, scope: str) -> list[DetectedError]:
    found: list[DetectedError] = []
    for m in _MISSPELLING_RX.finditer(text):
        word = m.group(1)
        found.append(
            DetectedError(
                "spelling",
                "spelling",
                word,
                match_case(word, MISSPELLINGS[word.lower()]),
                "Spelling error. Check the correct spelling and add the word to your review list.",
                "medium",
                m.start(1),
                m.end(1),
                "misspelling",
            )
        )
    if scope == "academic":
        for m in _CONTRACTION_RX.finditer(text):
            original = m.group(1)
            key = original.lower().replace("’", "'")
            replacement = CONTRACTIONS.get(key, original)
            following = text[m.end() : m.end() + 6].lower()
            if key == "it's" and following.startswith(" been"):
                replacement = "it has"
            found.append(
                DetectedError(
                    "academic_style",
                    "contractions",
                    original,
                    match_case(original, replacement),
                    "Avoid contractions in formal/academic writing; write the full form.",
                    "low",
                    m.start(1),
                    m.end(1),
                    "contraction",
                )
            )
        for m in _INFORMAL_RX.finditer(text):
            original = m.group(1)
            replacement = INFORMAL.get(original.lower(), "a large number of")
            if original.lower() == "a bunch of":
                replacement = "a number of"
            found.append(
                DetectedError(
                    "academic_style",
                    "informal_register",
                    original,
                    match_case(original, replacement),
                    "This word is informal. Choose a more formal alternative in academic writing.",
                    "low",
                    m.start(1),
                    m.end(1),
                    "informal",
                )
            )
    return found


def _fragment_detections(text: str) -> list[DetectedError]:
    """'Because they are cheap.' as a separate sentence is a fragment: join it to the main clause."""
    found: list[DetectedError] = []
    sentences = split_sentences(text)
    cursor = 0
    previous: tuple[int, int, str] | None = None
    for sentence in sentences:
        start = text.find(sentence, cursor)
        if start == -1:
            continue
        end = start + len(sentence)
        cursor = end
        first = sentence.split(" ", 1)[0].strip("\"'").lower()
        if (
            previous is not None
            and first in ("because", "although", "whereas", "which")
            and "," not in sentence
            and len(words(sentence)) <= 14
            and sentence.endswith(".")
        ):
            p_start, p_end, p_text = previous
            if p_text.endswith(".") and "\n" not in text[p_start:start]:
                last_word = re.search(r"(\S+)\.$", p_text)
                if last_word:
                    span_start = p_start + last_word.start(1)
                    span_end = start + len(sentence.split(" ", 1)[0])
                    original = text[span_start:span_end]
                    corrected = last_word.group(1) + " " + first
                    found.append(
                        DetectedError(
                            "grammar",
                            "sentence_structure",
                            original,
                            corrected,
                            f"A clause beginning with '{first}' cannot stand alone as a sentence. Join it to the main clause.",
                            "medium",
                            span_start,
                            span_end,
                            "fragment",
                        )
                    )
        previous = (start, end, sentence)
    return found


def _sentence_for(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start), text.rfind("\n", 0, start))
    right_candidates = [i for i in (text.find(".", end), text.find("!", end), text.find("?", end), text.find("\n", end)) if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return text[left + 1 : right].strip()[:400]


def detect_errors(text: str, *, mode: str = "writing", academic: bool = True) -> list[DetectedError]:
    """Run all rules. mode: 'writing' or 'speaking'. `academic` enables formal-register rules."""
    if not text or not text.strip():
        return []
    scope = "academic" if (academic and mode == "writing") else mode
    detections: list[DetectedError] = []
    for rule in RULES:
        if rule.scope == "academic" and scope != "academic":
            continue
        if rule.scope == "writing" and mode == "speaking":
            continue
        for m in rule.pattern.finditer(text):
            if rule.guard and not rule.guard(m, text):
                continue
            original = m.group(0)
            try:
                corrected = rule.fix(m)
            except (KeyError, IndexError):
                continue
            if not corrected or corrected.strip().lower() == original.strip().lower():
                continue
            detections.append(
                DetectedError(
                    rule.category,
                    rule.subcategory,
                    original.strip(),
                    corrected.strip(),
                    rule.explanation,
                    rule.severity,
                    m.start() + (len(original) - len(original.lstrip())),
                    m.start() + len(original.rstrip()),
                    rule.rule_id,
                )
            )
    if mode == "writing":
        detections.extend(_fragment_detections(text))
    detections.extend(_special_detections(text, scope if mode == "writing" else "speaking"))

    # Overlaps: identical-subcategory duplicates are dropped; distinct errors are all kept, but only
    # the first of an overlapping group keeps highlight offsets (the UI highlights non-overlapping spans).
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    detections.sort(key=lambda d: (d.start, severity_rank.get(d.severity, 3), -(d.end - d.start)))
    result: list[DetectedError] = []
    highlighted_until = -1
    for det in detections:
        det.context = _sentence_for(text, det.start, det.end)
        duplicate = any(r.subcategory == det.subcategory and r.start < det.end and det.start < r.end for r in result)
        if duplicate:
            continue
        if det.start < highlighted_until:
            det.highlight = False
        else:
            highlighted_until = det.end
        result.append(det)
    return result
