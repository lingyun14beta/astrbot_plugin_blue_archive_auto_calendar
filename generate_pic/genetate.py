import asyncio
import datetime
import math
import time

import aiohttp
from .gamekee_calendar import transform_gamekee_calendar
from .draw import create_image, draw_item, draw_title
from astrbot.api import logger


event_data = {
    'jp': [],
    'cn': [],
    'global': [],
}

lock = {
    'jp': asyncio.Lock(),
    'cn': asyncio.Lock(),
    'global': asyncio.Lock(),
}

event_updated = {
    'jp': '',
    'cn': '',
    'global': '',
}

data_source = {
    'jp': 'gamekee',
    'cn': 'gamekee',
    'global': 'gamekee',
}

gamekee_server_id = {
    'jp': '15',
    'cn': '16',
    'global': '17',
}

server_name = {
    'jp': '日服',
    'cn': '国服',
    'global': '国际服',
}

GAMEKEE_URL = 'https://www.gamekee.com/v1/wiki/indexV2'
GAMEKEE_POOL_URL = 'https://www.gamekee.com/v1/cardPool/query-list?order_by=-1&card_tag_id=&keyword=&kind_id=6&status=0&serverId={sid}'


async def load_event_gamekee(server):
    try:
        sid = gamekee_server_id[server]
        server_cn = server_name[server]
        gamekee_data_events = []
        gamekee_data_pools = []

        async with aiohttp.ClientSession() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            session.headers['Game-Alias'] = 'ba'

            # 活动周历
            async with session.get(GAMEKEE_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(f'gamekee indexV2 返回 HTTP {resp.status}')
                    return 1
                res = await resp.json(content_type=None)
                for module in res.get("data", []):
                    if module["module"]["name"] == "活动周历":
                        raw = module["list"]
                        if isinstance(raw, dict):
                            gamekee_data_events = raw.get(sid, [])
                        else:
                            gamekee_data_events = [i for i in raw if server_cn in i.get("pub_area", "")]
                        break

            # 卡池
            pool_url = GAMEKEE_POOL_URL.format(sid=sid)
            async with session.get(pool_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    res = await resp.json(content_type=None)
                    pool_dic = {}
                    for pool in res.get("data", []):
                        if pool["end_at"] > time.time():
                            pool_dic.setdefault(str(pool["end_at"]), []).append(pool)
                        else:
                            break
                    for pools in pool_dic.values():
                        names = [p["name"] for p in pools]
                        if names:
                            gamekee_data_pools.append({
                                "title": f"卡池：{'、'.join(names)}",
                                "begin_at": pools[0]["start_at"],
                                "end_at": pools[0]["end_at"],
                                "pub_area": server_cn,
                            })

        all_data = gamekee_data_events + gamekee_data_pools
        if not all_data:
            logger.warning(f'gamekee {server} 数据为空')
            return 1

        data = transform_gamekee_calendar(server, all_data)
        if not data:
            logger.warning(f'gamekee {server} 数据解析为空')
            return 1

    except Exception as e:
        logger.error(f'gamekee {server} 数据获取异常: {e}')
        return 1

    event_data[server] = []
    for item in data:
        start_time = datetime.datetime.fromtimestamp(item["start"])
        end_time = datetime.datetime.fromtimestamp(item["end"])
        event = {'title': item['title'], 'start': start_time, 'end': end_time, 'type': 1}
        if '倍' in event['title']:
            event['type'] = 2
        elif '总力' in event['title'] or '演习' in event['title']:
            event['type'] = 3
        event_data[server].append(event)
    return 0


async def load_event(server):
    flag = await load_event_gamekee(server)
    if flag == 0 and event_data[server]:
        data_source[server] = 'gamekee'
        logger.info(f'获取 gamekee {server_name[server]} 信息成功')
        return 0
    logger.error(f'{server_name[server]} 数据获取失败')
    return 1


async def get_events(server, offset, days):
    ba_now = datetime.datetime.now()
    if ba_now.hour < 4:
        ba_now -= datetime.timedelta(days=1)
    ba_now = ba_now.replace(hour=18, minute=0, second=0, microsecond=0)

    async with lock[server]:
        t = ba_now.strftime('%y%m%d')
        if event_updated[server] != t:
            if await load_event(server) == 0:
                event_updated[server] = t

    start = ba_now + datetime.timedelta(days=offset)
    end = start + datetime.timedelta(days=days) - datetime.timedelta(hours=8)

    events = []
    for event in event_data[server]:
        if end > event['start'] and start < event['end']:
            ev = dict(event)
            ev['start_days'] = math.ceil((ev['start'] - start) / datetime.timedelta(days=1))
            ev['left_days'] = math.floor((ev['end'] - start) / datetime.timedelta(days=1))
            events.append(ev)

    events.sort(key=lambda e: e["type"] * 100 - e['left_days'], reverse=True)
    return events


def get_ba_now(offset):
    ba_now = datetime.datetime.now()
    if ba_now.hour < 4:
        ba_now -= datetime.timedelta(days=1)
    ba_now = ba_now.replace(hour=18, minute=0, second=0, microsecond=0)
    return ba_now + datetime.timedelta(days=offset)


async def generate_day_schedule(server='jp'):
    events = await get_events(server, 0, 7)
    logger.info(f'获取到 {len(events)} 个活动')

    has_prediction = any(e['start_days'] > 0 for e in events)
    title_len = max([25] + [len(e['title']) + 5 for e in events])

    if has_prediction:
        total_rows = 1 + len(events) + 1 + 1
    else:
        total_rows = 1 + len(events) + 1

    im = create_image(total_rows, title_len)
    ba_now = get_ba_now(0)
    draw_title(im, 0, f'碧蓝档案{server_name[server]}活动', ba_now.strftime('%Y/%m/%d'), '正在进行')

    if not events:
        draw_item(im, 1, 1, '无数据', 0)
        i = 2
    else:
        i = 1
        for event in events:
            if event['start_days'] <= 0:
                draw_item(im, i, event['type'], event['title'], event['left_days'])
                i += 1
        if has_prediction:
            draw_title(im, i, right='即将开始')
            i += 1
            for event in events:
                if event['start_days'] > 0:
                    draw_item(im, i, event['type'], event['title'], -event['start_days'])
                    i += 1

    draw_title(im, i, left=f'data by {data_source[server]}', right='bot by astrbot')
    return im
