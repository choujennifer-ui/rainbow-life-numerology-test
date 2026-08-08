
LINES = {
    "1-2-3": {"numbers": {1,2,3}, "name": "藝術線／任性線"},
    "4-5-6": {"numbers": {4,5,6}, "name": "組織線／完美主義"},
    "7-8-9": {"numbers": {7,8,9}, "name": "貴人線／權力線"},
    "1-4-7": {"numbers": {1,4,7}, "name": "物質線／負財線"},
    "2-5-8": {"numbers": {2,5,8}, "name": "感情線／饒舌線"},
    "3-6-9": {"numbers": {3,6,9}, "name": "智慧線／夢想線"},
    "1-5-9": {"numbers": {1,5,9}, "name": "事業線／工作狂線"},
    "3-5-7": {"numbers": {3,5,7}, "name": "人際關係線／爭寵線"},
    "2-4": {"numbers": {2,4}, "name": "靈巧線／詭詐線"},
    "2-6": {"numbers": {2,6}, "name": "公平待人線／利用他人線"},
    "6-8": {"numbers": {6,8}, "name": "親切誠實線／隱瞞感受線"},
    "4-8": {"numbers": {4,8}, "name": "工作模範線／內心不安線"},
}

def calculate_lines(birthday_digits: list[int], youth_digits: list[int]):
    presence = set(birthday_digits + youth_digits)
    results = []
    for line_id, line_info in LINES.items():
        if line_info["numbers"] <= presence:
            results.append({"id": line_id, "name": line_info["name"]})
    return results
