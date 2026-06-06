import re
import time


def extract_calendar_data(server, data):
    if server == "jp":
        flag = "日服"
        server_id = "15"
    elif server == "cn":
        flag = "国服"
        server_id = "16"
    else:
        flag = "国际服"
        server_id = "17"

    event_list = []

    # indexV2 返回的活动周历按服务器ID分组，data是dict {"15": [...], "16": [...], "17": [...]}
    # 兼容旧格式（list）和新格式（dict）
    if isinstance(data, dict):
        items = data.get(server_id, [])
    else:
        # 旧格式：list，每项有 pub_area 字段
        items = [item for item in data if flag in item.get("pub_area", "")]

    for item in items:
        try:
            title = item["title"]
            start_time = item["begin_at"]
            end_time = item["end_at"]

            if "卡池" in title:
                title = title.replace(flag, "")
            elif "维护" in title:
                st = time.strftime("%Y-%m-%d %H:%M", time.localtime(start_time))
                et = time.strftime("%H:%M", time.localtime(end_time))
                title = title.replace(flag, "") + st + " ~ " + et
            else:
                title = re.sub(r'【.*?】', "", title)

            event_list.append({
                'title': title,
                'start': start_time,
                'end': end_time,
            })
        except Exception:
            continue

    return event_list


def transform_gamekee_calendar(server, data):
    return extract_calendar_data(server, data)
