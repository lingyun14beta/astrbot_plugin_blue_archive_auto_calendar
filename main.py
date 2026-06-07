import asyncio
import os
from .generate_pic.genetate import generate_day_schedule
from datetime import datetime, timedelta
import json

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api import AstrBotConfig

VALID_SERVERS = {'jp', 'cn', 'global'}


def get_umo_file_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.path.join(current_dir, '..', '..')
    file_path = os.path.join(plugin_root, 'plugin_data', 'schaledb_calendar', 'umo.json')
    return os.path.normpath(file_path)


def load_umo_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_umo_data(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        asyncio.create_task(self.set_schedule())

    @filter.command("日历")
    async def send_calendar(self, event: AstrMessageEvent, server: str):
        if server not in VALID_SERVERS:
            yield event.plain_result("无效的服务器参数，请使用 jp / cn / global")
            return
        img = await generate_day_schedule(server)
        temp_dir = ".temp"
        os.makedirs(temp_dir, exist_ok=True)
        img_path = os.path.join(temp_dir, f"{server}_pic.png")
        img.save(img_path, "PNG")
        logger.info(f"{event.unified_msg_origin} 图片发送成功")
        yield event.image_result(img_path)

    @filter.command("启用日历")
    async def switch_on(self, event: AstrMessageEvent, server: str):
        """
        启用日历推送
        server: jp / cn / global，多个服务器用 / 分隔，如 cn/jp
        """
        if not server:
            yield event.plain_result("请指定服务器，如：启用日历 cn")
            return
        for s in server.split('/'):
            if s not in VALID_SERVERS:
                yield event.plain_result(f"无效的服务器参数 {s}，请使用 jp / cn / global")
                return
        try:
            file_path = get_umo_file_path()
            data_dict = load_umo_data(file_path)
            umo = event.unified_msg_origin
            data_dict[umo] = server
            save_umo_data(file_path, data_dict)
            logger.info(f'启用日历: {umo} -> {server}')
        except Exception as e:
            logger.error(f'启用日历出错：{e}')
            yield event.plain_result(f"启用失败：{e}")
            return
        yield event.plain_result(f"已启用本聊天 {server} 日历推送")

    @filter.command("禁用日历")
    async def switch_off(self, event: AstrMessageEvent):
        """禁用日历推送"""
        try:
            file_path = get_umo_file_path()
            data_dict = load_umo_data(file_path)
            umo = event.unified_msg_origin
            if umo not in data_dict:
                yield event.plain_result("本聊天未启用日历推送")
                return
            del data_dict[umo]
            save_umo_data(file_path, data_dict)
            logger.info(f'禁用日历: {umo}')
        except Exception as e:
            logger.error(f'禁用日历出错: {e}')
            yield event.plain_result(f"禁用失败：{e}")
            return
        yield event.plain_result("已禁用日历推送")

    async def send(self, umo, server):
        img = await generate_day_schedule(server)
        temp_dir = ".temp"
        os.makedirs(temp_dir, exist_ok=True)
        img_path = os.path.join(temp_dir, f"{server}_pic.png")
        img.save(img_path, "PNG")
        message_chain = MessageChain().file_image(img_path)
        await self.context.send_message(umo, message_chain)
        logger.info(f"{umo} 定时图片发送成功")

    async def set_schedule(self):
        auto_send_time = self.config.get("auto_send_time", "09:00")
        file_path = get_umo_file_path()
        group_ids_and_servers = load_umo_data(file_path)
        logger.info(f"读取推送配置成功，共 {len(group_ids_and_servers)} 个会话")
        try:
            await self.schedule_send_loop(auto_send_time, group_ids_and_servers)
        except Exception as e:
            logger.error(f"定时任务启动失败: {e}")

    async def schedule_send_loop(self, auto_send_time, group_ids_and_servers):
        while True:
            try:
                now = datetime.now()
                target_time = datetime.strptime(auto_send_time, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )
                if now >= target_time:
                    target_time += timedelta(days=1)
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"下次推送时间: {target_time}，等待 {wait_seconds:.0f} 秒")
                await asyncio.sleep(wait_seconds)

                for umo, servers in group_ids_and_servers.items():
                    for server in servers.split("/"):
                        if server in {'jp', 'cn', 'global'}:
                            await self.send(umo, server)
                            logger.info(f"定时发送完成: {umo} {server}")
            except Exception as e:
                logger.error(f"定时发送错误: {e}")
                await asyncio.sleep(300)
