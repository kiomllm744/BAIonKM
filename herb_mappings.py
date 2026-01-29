"""
Korean-English Herb Name Mappings.
This module provides bilingual support for herb names.
Maps Korean (한글) names to English (Pinyin) names and vice versa.
"""

# Herb name mappings: English (Pinyin) -> Korean (한글)
# Complete list of 437 herbs from the database
HERB_NAME_MAPPINGS = {
    "a wei": "아위",
    "ai ye": "애엽",
    "an xi xiang": "안식향",
    "ba dou": "파두",
    "ba ji tian": "파극천",
    "ba jiao hui xiang": "팔각회향",
    "bai bian dou": "백편두",
    "bai bu": "백부근",
    "bai dou kou": "백두구",
    "bai fu zi": "백부자",
    "bai guo": "백과 (은행)",
    "bai guo ye": "백과엽 (은행잎)",
    "bai he": "백합",
    "bai hua she": "백화사",
    "bai hua she she cao": "백화사설초",
    "bai ji": "백급",
    "bai jiang": "패장",
    "bai jiang can": "백강잠",
    "bai lian": "백렴",
    "bai qu cai": "백굴채",
    "bai shao yao": "백작약",
    "bai shou wu": "백수오",
    "bai tou weng": "백두옹",
    "bai wei": "백미",
    "bai xian pi": "백선피",
    "bai zhi": "백지",
    "bai zhu": "백출",
    "bai zi ren": "백자인",
    "ban bian lian": "반변련",
    "ban lan gen": "판람근",
    "ban mao": "반묘",
    "ban xia": "반하",
    "ban zhi lian": "반지련",
    "bei sha shen": "북사삼",
    "bi ba": "필발",
    "bi cheng qie": "필징가",
    "bi ma zi": "피마자",
    "bi xie": "비해",
    "bian xu": "편축",
    "bie jia": "별갑",
    "bing lang": "빈랑",
    "bing pian": "빙편 (용뇌)",
    "bo he": "박하",
    "bo ye da huang": "파엽대황",
    "bu gu zhi": "보골지",
    "cang er zi": "창이자",
    "cang zhu": "창출",
    "cao dou kou": "초두구",
    "cao guo": "초과",
    "cao wu": "초오",
    "ce bai ye": "측백엽",
    "chai hu": "시호",
    "chan su": "섬수",
    "chan tui": "선태",
    "chang pu": "창포",
    "chang shan": "상산",
    "che qian cao": "차전초",
    "che qian zi": "차전자",
    "chen pi": "진피",
    "chen xiang": "침향",
    "cheng liu": "정류",
    "chi dou": "적두",
    "chong wei zi": "충위자",
    "chu bai pi": "저백피",
    "chuan bei mu": "천패모",
    "chuan lian zi": "천련자",
    "chuan shan jia": "천산갑",
    "chuan wu": "오두",
    "chuan xiong": "천궁",
    "ci wu jia": "자오가",
    "cong bai": "총백",
    "da feng zi": "대풍자",
    "da huang": "대황",
    "da qing ye": "대청엽",
    "da suan": "대산 (마늘)",
    "da zao": "대조",
    "dan nan xing": "담남성",
    "dan shen": "단삼",
    "dan zhu ye": "담죽엽",
    "dang gui": "당귀",
    "dang shen": "당삼 (만삼)",
    "dang yao": "당약",
    "deng xin cao": "등심초",
    "di fu zi": "지부자",
    "di gu pi": "지골피",
    "di huang": "지황",
    "di yu": "지유",
    "ding gong teng": "정공등",
    "ding xiang": "정향",
    "dong chong xia cao": "동충하초",
    "dong gua pi": "동과피",
    "dong gua zi": "동과자",
    "dong kui zi": "동규자",
    "dou chi": "두시",
    "dou kou": "두구",
    "du huo": "독활",
    "du zhong": "두충",
    "du zhong ye": "두충엽",
    "e jiao": "아교",
    "e zhu": "아출",
    "fan xie ye": "번사엽",
    "fang feng": "방풍",
    "fang ji": "방기",
    "fei zi": "비자",
    "fu ling": "복령",
    "fu pen zi": "복분자",
    "fu ping": "부평",
    "fu shen": "복신",
    "fu xiao mai": "부소맥",
    "fu zi": "부자",
    "gan cao": "감초",
    "gan jiang": "건강",
    "gan song": "감송",
    "gan sui": "감수",
    "gao ben": "고본",
    "gao liang jiang": "고량강",
    "ge gen": "갈근",
    "ge hua": "갈화",
    "ge jie": "합개",
    "gou ji": "구척",
    "gou qi zi": "구기자",
    "gou shu guo": "구수",
    "gou teng": "조구등",
    "gu sui bu": "골쇄보",
    "gu ya": "곡아",
    "gua di": "과체",
    "gua lou zi": "과루인",
    "guan zhong": "관중",
    "guang huo xiang": "광곽향",
    "guang jin qian cao": "광금전초",
    "gui ban": "구판",
    "gui jian yu": "귀전우",
    "gui zhi": "계지",
    "hai dai": "해대",
    "hai feng teng": "해풍등",
    "hai fu shi": "해부석",
    "hai jin sha": "해금사",
    "hai ma": "해마",
    "hai piao xiao": "해표초",
    "hai ren cao": "해인초",
    "hai shen": "해삼",
    "hai song zi": "해송자",
    "hai tong pi": "해동피",
    "hai zao": "해조",
    "han shui shi": "한수석",
    "he huan pi": "합환피",
    "he shi": "학슬",
    "he shou wu": "하수오",
    "he ye": "하엽",
    "he zi": "가자",
    "hei dou": "흑두",
    "hei zhi ma": "흑지마",
    "hong hua": "홍화",
    "hong shen": "홍삼",
    "hou pu": "후박",
    "hu huang lian": "호황련",
    "hu ji sheng": "곡기생",
    "hu jiao": "호초",
    "hu lu ba": "호로파",
    "hu tao ren": "호도",
    "hu zhang": "호장근",
    "hua mu pi": "화피",
    "hua shi": "활석",
    "huai hua": "괴화",
    "huai jiao": "괴각",
    "huang bai": "황백",
    "huang jing": "황정",
    "huang lian": "황련",
    "huang qi": "황기",
    "huang qin": "황금",
    "hui xiang": "회향",
    "huo ma ren": "마인",
    "huo xiang": "곽향",
    "ji li": "질려",
    "ji nei jin": "계내금",
    "ji xing zi": "급성자",
    "ji xue teng": "계혈등",
    "jiang huang": "강황",
    "jiang xiang": "강향",
    "jie geng": "길경 (도라지)",
    "jie gu mu": "접골목",
    "jie zi": "개자",
    "jin qian cao": "금전초",
    "jin que gen": "골담초",
    "jin yin hua": "금은화",
    "jin ying zi": "금앵자",
    "jing da ji": "대극",
    "jing jie": "형개",
    "jing mi": "갱미",
    "jiu zi": "구자",
    "ju he": "귤핵",
    "ju hua": "국화",
    "juan bai": "권백",
    "jue ming zi": "결명자",
    "ku lian pi": "고련피",
    "ku mu": "고목",
    "ku shen": "고삼",
    "kuan dong hua": "관동화",
    "kun bu": "곤포",
    "la jiao": "번초",
    "lai fu zi": "나복자",
    "lang du": "낭독",
    "lao guan cao": "현초",
    "li lu": "여로",
    "li zhi he": "여지핵",
    "lian qian cao": "연전초",
    "lian qiao": "연교",
    "lian zi": "연자",
    "lian zi xin": "연자심",
    "lie dang": "초종용",
    "ling xiang cao": "영릉향",
    "ling xiao hua": "능소화",
    "ling yang jiao": "영양각",
    "ling zhi": "영지",
    "liu huang": "유황",
    "liu ji nu": "유기노",
    "liu ye bai qian": "백전",
    "long dan": "용담",
    "long gu": "용골",
    "long kui": "용규",
    "long ya cao": "용아초",
    "long yan rou": "용안육",
    "lou lu": "누로",
    "lu cao": "노초",
    "lu dou": "녹두",
    "lu gen": "노근",
    "lu hui": "노회",
    "lu jiao": "녹각",
    "lu jiao jiao": "녹각교",
    "lu lu tong": "노로통",
    "lu rong": "녹용",
    "luo shi teng": "낙석등",
    "lv cao": "율초",
    "lv dou": "녹두",
    "lv song guo": "보두",
    "ma bian cao": "마편초",
    "ma bo": "마발",
    "ma chi xian": "마치현",
    "ma huang": "마황",
    "ma huang gen": "마황근",
    "ma qian zi": "마전 자",
    "mai dong": "맥문동",
    "mai ya": "맥아",
    "man jing zi": "만형자",
    "man tuo luo ye": "만타라엽",
    "mang xiao": "망초",
    "mao gen": "백모근",
    "mei gui hua": "매괴화",
    "mi meng hua": "밀몽화",
    "mo han lian": "한련초",
    "mo yao": "몰약",
    "mu bie zi": "목별자",
    "mu dan pi": "목단피",
    "mu fang ji": "목방기",
    "mu gua": "모과",
    "mu jin pi": "목근피",
    "mu li": "모려",
    "mu tian liao": "목천료",
    "mu tong": "목통",
    "mu xiang": "목향",
    "mu zei": "목적",
    "niu bang gen": "우방근",
    "niu bang zi": "우방자",
    "niu dan": "우담",
    "niu huang": "우황",
    "niu xi": "우슬",
    "nv zhen zi": "여정실",
    "ou jie": "우절",
    "pang da hai": "반대해",
    "pei lan": "패란",
    "pi pa ye": "비파엽",
    "po gu zhi": "파고지 (보골지)",
    "pu gong ying": "포공영",
    "pu huang": "포황",
    "qian cao": "천초",
    "qian cao gen": "천초근",
    "qian hu": "전호",
    "qian jin zi": "속수자",
    "qian nian jian": "천년건",
    "qian niu zi": "견우자",
    "qian shi": "검실",
    "qiang huo": "강활",
    "qin jiao": "진교",
    "qin pi": "진피 (물푸레나무)",
    "qing dai": "청대",
    "qing hao": "청호",
    "qing pi": "청피",
    "qiu yin": "구인 (지렁이)",
    "qu mai": "구맥",
    "quan shen": "권삼",
    "quan xie": "전갈",
    "ren dong teng": "인동등",
    "ren shen": "인삼",
    "ri ben dang gui": "일본당귀",
    "rou cong rong": "육종용",
    "rou dou kou": "육두구",
    "rou gui": "육계",
    "ru xiang": "유향",
    "san bai cao": "삼백초",
    "san leng": "삼릉",
    "san qi": "삼칠",
    "sang bai pi": "상백피",
    "sang ji sheng": "상기생",
    "sang piao xiao": "상표초",
    "sang shen": "상심 (오디)",
    "sang ye": "상엽",
    "sang zhi": "상지",
    "sha ren": "사인",
    "shan ci gu": "산자고",
    "shan dou gen": "산두근",
    "shan nai": "산내",
    "shan yao": "산약 (마)",
    "shan zha": "산사",
    "shan zhu yu": "산수유",
    "shang lu": "상륙",
    "she chuang zi": "사상자",
    "she gan": "사간",
    "she xiang": "사향",
    "she xiang cao": "사향초",
    "sheng di huang": "생지황",
    "sheng jiang": "생강",
    "sheng ma": "승마",
    "shi chang pu": "석창포",
    "shi di": "시체",
    "shi hu": "석곡",
    "shi jue ming": "석결명",
    "shi jun zi": "사군자",
    "shi liu": "석류",
    "shi liu pi": "석류피",
    "shi luo zi": "시라자",
    "shi wei": "석위",
    "shi yan": "석연",
    "shou wu teng": "수오등",
    "shu di huang": "숙지황",
    "shu jiao": "산초",
    "shu kui hua": "촉규화",
    "shui zhi": "수질",
    "si gua luo": "사과락",
    "su he xiang": "소합향",
    "su mu": "소목",
    "suan zao ren": "산조인",
    "suo yang": "쇄양",
    "tan xiang": "백단향",
    "tao ren": "도인",
    "teng huang": "등황",
    "tian hua fen": "천화분",
    "tian ma": "천마",
    "tian men dong": "천문동",
    "tian nan xing": "천남성",
    "tian zhu huang": "천죽황",
    "ting li zi": "정력자",
    "tong cao": "통초",
    "tou gu cao": "투골초",
    "tu fu ling": "토복령",
    "tu gen": "토근",
    "tu mu xiang": "토목향",
    "tu si zi": "토사자",
    "wa leng zi": "와릉자",
    "wang bu liu xing": "왕불류행",
    "wei ling cai": "위릉채",
    "wei ling xian": "위령선",
    "wu bei zi": "오배자",
    "wu gong": "오공",
    "wu jia pi": "오가피",
    "wu ling zhi": "오령지",
    "wu mei": "오매",
    "wu wei zi": "오미자",
    "wu yao": "오약",
    "wu zhu yu": "오수유",
    "xi hong hua": "번홍화",
    "xi xian": "희렴",
    "xi xin": "세신",
    "xia ku cao": "하고초",
    "xian mao": "선모",
    "xiang fu": "향부자",
    "xiang ru": "향유",
    "xiao ji": "소계",
    "xie bai": "해백",
    "xie cao": "힐초",
    "xin yi": "신이",
    "xing ren": "행인",
    "xiong dan": "웅담",
    "xu chang qing": "서장경",
    "xu duan": "속단",
    "xuan cao gen": "훤초근",
    "xuan fu hua": "선복화",
    "xuan shen": "현삼",
    "xue jie": "혈갈",
    "ya ma": "아마인",
    "yan hu suo": "현호색",
    "yang cong": "양파",
    "yang di huang ye": "양지황",
    "yang ti gen": "양제근",
    "ye ju": "감국",
    "ye ming sha": "야명사",
    "yi mu cao": "익모초",
    "yi tang": "교이",
    "yi yi ren": "의이인",
    "yi zhi ren": "익지인",
    "yin chai hu": "은시호",
    "yin chen hao": "인진호",
    "yin yang huo": "음양곽",
    "yu bai pi": "유백피",
    "yu jin": "울금",
    "yu li ren": "욱리인",
    "yu xing cao": "어성초",
    "yu zhi zi": "예지자",
    "yu zhu": "옥죽",
    "yuan can sha": "잠사",
    "yuan hua": "원화",
    "yuan zhi": "원지",
    "yun tai zi": "운대자",
    "zao jia": "조협",
    "ze lan": "택란",
    "ze xie": "택사",
    "zhang nao": "장뇌",
    "zhe bei mu": "절패모",
    "zhe chong": "자충",
    "zhen zhu": "진주",
    "zhi ju zi": "지구자",
    "zhi ke": "지각",
    "zhi ma": "흑지마",
    "zhi mu": "지모",
    "zhi qiao": "지각 (동의어)",
    "zhi shi": "지실",
    "zhi zi": "치자",
    "zhu dan": "저담",
    "zhu li": "죽력",
    "zhu ling": "저령",
    "zhu ma gen": "저마근",
    "zi cao": "자초",
    "zi hua di ding": "자화지정",
    "zi su ye": "자소엽",
    "zi su zi": "자소자",
    "zi tan xiang": "자단향",
    "zi wan": "자완",
    "zong lv pi": "종려피",
}

# Create reverse mapping (Korean -> English) for fast lookups
KOREAN_TO_ENGLISH = {}
for english, korean in HERB_NAME_MAPPINGS.items():
    # Handle Korean names with parentheses (e.g., "백과 (은행)" -> map both "백과" and "백과 (은행)")
    KOREAN_TO_ENGLISH[korean] = english
    # Also map the base Korean name without parentheses
    if "(" in korean:
        base_korean = korean.split("(")[0].strip()
        if base_korean not in KOREAN_TO_ENGLISH:
            KOREAN_TO_ENGLISH[base_korean] = english

# Also create a lowercase version for case-insensitive matching
ENGLISH_TO_KOREAN_LOWER = {k.lower(): v for k, v in HERB_NAME_MAPPINGS.items()}


def get_korean_name(english_name: str) -> str:
    """Get Korean name for an English herb name."""
    return HERB_NAME_MAPPINGS.get(english_name, ENGLISH_TO_KOREAN_LOWER.get(english_name.lower(), ""))


def get_english_name(korean_name: str) -> str:
    """Get English name for a Korean herb name."""
    # Try exact match first
    if korean_name in KOREAN_TO_ENGLISH:
        return KOREAN_TO_ENGLISH[korean_name]
    # Try without parentheses
    base_korean = korean_name.split("(")[0].strip() if "(" in korean_name else korean_name
    return KOREAN_TO_ENGLISH.get(base_korean, "")


def search_herbs_bilingual(query: str, all_english_names: list) -> list:
    """
    Search herbs in both Korean and English.
    Returns list of dicts: [{'english': 'huang qi', 'korean': '황기'}, ...]
    """
    query = query.strip()
    query_lower = query.lower()
    results = []
    seen = set()
    
    # Check if query is Korean (contains Hangul characters)
    is_korean_query = any('\uac00' <= char <= '\ud7a3' for char in query)
    
    # Create a set of lowercase English names for fast lookup
    all_english_lower = {n.lower(): n for n in all_english_names}
    
    if is_korean_query:
        # Search in Korean names
        for korean, english in KOREAN_TO_ENGLISH.items():
            if query in korean and english.lower() not in seen:
                # Verify it exists in database
                if english.lower() in all_english_lower:
                    actual_english = all_english_lower[english.lower()]
                    results.append({
                        'english': actual_english,
                        'korean': get_korean_name(actual_english),
                        'match_type': 'korean'
                    })
                    seen.add(english.lower())
    else:
        # Search in English names
        for english_name in all_english_names:
            english_lower = english_name.lower()
            if query_lower in english_lower and english_lower not in seen:
                korean = get_korean_name(english_name)
                results.append({
                    'english': english_name,
                    'korean': korean,
                    'match_type': 'english'
                })
                seen.add(english_lower)
    
    # Sort by relevance
    def relevance_score(item):
        name = item['korean'] if is_korean_query else item['english']
        name_lower = name.lower() if not is_korean_query else name
        q = query if is_korean_query else query_lower
        
        if name_lower == q:
            return (0, len(name), name_lower)
        elif name_lower.startswith(q):
            return (1, len(name), name_lower)
        else:
            pos = name_lower.find(q)
            return (2, pos if pos >= 0 else 999, len(name), name_lower)
    
    results.sort(key=relevance_score)
    return results


def validate_herb_bilingual(name: str, all_english_names: list) -> dict:
    """
    Validate a herb name (Korean or English) and return the canonical English name.
    Returns: {'valid': bool, 'english': str, 'korean': str}
    """
    name = name.strip()
    
    # Create a set of lowercase English names for fast lookup
    all_english_lower = {n.lower(): n for n in all_english_names}
    
    # Check if it's Korean
    is_korean = any('\uac00' <= char <= '\ud7a3' for char in name)
    
    if is_korean:
        # Try to find English equivalent
        english = get_english_name(name)
        if english and english.lower() in all_english_lower:
            actual_english = all_english_lower[english.lower()]
            return {'valid': True, 'english': actual_english, 'korean': get_korean_name(actual_english)}
    else:
        # Try to find in English names (case-insensitive)
        if name.lower() in all_english_lower:
            actual_english = all_english_lower[name.lower()]
            korean = get_korean_name(actual_english)
            return {'valid': True, 'english': actual_english, 'korean': korean}
    
    return {'valid': False, 'english': '', 'korean': ''}
