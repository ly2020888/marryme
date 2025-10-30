import random
import time
from nonebot import get_driver, on_command, require
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment, GroupMessageEvent
from nonebot.adapters.onebot.v11.message import Message
from nonebot.params import CommandArg
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import SceneType, Session, UniSession, QryItrface
import asyncio
from datetime import datetime, timedelta

from .MarriageManager import MarriageManager
from loguru import logger

# 全局管理器实例
marriage_manager = MarriageManager()

# 创建命令处理器
marry_cmd = on_command("结婚", aliases={"求婚", "marry", "娶"}, priority=10, block=True)
accept_cmd = on_command(
    "同意", aliases={"接受", "我愿意", "我同意"}, priority=10, block=True
)
reject_cmd = on_command(
    "拒绝", aliases={"不同意", "不要", "不行"}, priority=10, block=True
)
check_marriage_cmd = on_command(
    "婚姻状态", aliases={"查看婚姻", "marriage", "我的婚姻"}, priority=10, block=True
)
divorce_cmd = on_command(
    "离婚", aliases={"分手", "分手吧", "离婚吧"}, priority=10, block=True
)
have_baby_cmd = on_command(
    "生宝宝",
    aliases={"生孩子", "生娃", "baby", "做爱", "爱爱", "sex", "sox"},
    priority=10,
    block=True,
)
check_babies_cmd = on_command(
    "我的宝宝", aliases={"宝宝列表", "查看宝宝", "babies"}, priority=10, block=True
)
preference_cmd = on_command(
    "婚姻设置", aliases={"偏好", "preference"}, priority=10, block=True
)


@marry_cmd.handle()
async def handle_marry(
    bot: Bot,
    event: GroupMessageEvent,
    session: Session = UniSession(),
    interface: QryItrface = None,
    args: Message = CommandArg(),
):
    """处理结婚请求"""
    # 获取消息中的at对象
    group_id = str(event.group_id)
    at_targets = []
    for segment in event.message:
        if segment.type == "at":
            qq = segment.data.get("qq")
            if qq and qq != "all":
                at_targets.append(qq)

    if not at_targets:
        await marry_cmd.finish("请@你想要结婚的对象！")

    if len(at_targets) > 1:
        await marry_cmd.finish("一次只能向一个人求婚哦！")

    target_id = at_targets[0]

    # 检查是否和自己结婚
    if target_id == str(event.user_id):
        await marry_cmd.finish("你不能和自己结婚哦！")

    target_pref = await marriage_manager.get_user_preference(target_id, group_id)
    if target_pref and target_pref["allow_marriage"] is False:
        await marry_cmd.finish(
            f"{target_pref.get('user_name', '对方')}设置了不允许结婚"
        )

    # # 检查是否已有婚姻
    # existing_marriage = await marriage_manager.get_user_marriage(str(event.user_id))
    # if existing_marriage:
    #     await marry_cmd.finish("你已经结过婚了！")

    # target_marriage = await marriage_manager.get_user_marriage(target_id)
    # if target_marriage:
    #     await marry_cmd.finish("对方已经结过婚了！")

    # 获取用户信息
    try:
        members = await interface.get_members(SceneType.GROUP, str(event.group_id))

        proposer_info = next(
            (m.user for m in members if m.user.id == str(event.user_id)), None
        )
        target_info = next((m.user for m in members if m.user.id == target_id), None)

        if not target_info:
            await marry_cmd.finish(
                "未在群聊中找到指定的用户！请确认@的是正确的群成员。"
            )
        # 获取头像URL
        logger.info(f"用户信息: {target_info}")  # 添加日志

        target_avatar_url = target_info.avatar

        avatar_image = None
        if target_avatar_url:
            logger.info(f"开始下载头像: {target_avatar_url}")  # 添加日志
            avatar_image = await marriage_manager.download_avatar_as_image(
                target_avatar_url
            )
        else:
            logger.warning("未获取到头像URL")  # 添加日志
        # 创建结婚请求
        request_id = await marriage_manager.create_marriage_request(
            proposer_id=str(event.user_id),
            proposer_name=proposer_info.name or proposer_info.id,
            target_id=target_id,
            target_name=target_info.name or target_info.id,
            group_id=str(event.group_id),
        )

        # 构建消息
        message_parts = [
            f"💌结婚请求",
            f"{proposer_info.name or proposer_info.id} 向 {target_info.name or target_info.id} 发起了结婚请求！",
            f"💌对方信息：",
            f"ID：{target_info.id}",
            f"昵称：{target_info.name or '未知'}",
        ]

        if avatar_image:
            message_parts.append(avatar_image)  # 直接插入图片消息段

        message_parts.extend(
            [
                f"",
                f"请被求婚者在120秒内回复：",
                f"'同意' 或 '我愿意' - 接受求婚",
                f"'拒绝' 或 '不同意' - 拒绝求婚",
                f"",
                f"{MessageSegment.at(target_id)} 你愿意接受这份爱意吗？",
            ]
        )

        await marry_cmd.send(Message(message_parts))

        # 设置120秒后自动取消
        async def expire_request():
            await asyncio.sleep(120)
            # 检查请求是否仍然存在且未被处理
            request = await marriage_manager.get_pending_request_by_id(request_id)
            if request:
                await marriage_manager.reject_marriage_request(request_id)
                await marry_cmd.send(
                    f"💔 {proposer_info.name or proposer_info.id} 向 {target_info.name or target_info.id} 的结婚请求已超时取消。"
                )

        asyncio.create_task(expire_request())

    except ValueError as e:
        await marry_cmd.finish(f"发起结婚请求失败：{e}")
    except Exception as e:
        await marry_cmd.finish(f"发起结婚请求失败：{e}")


@accept_cmd.handle()
async def handle_accept(
    bot: Bot,
    event: GroupMessageEvent,
    session: Session = UniSession(),
    args: Message = CommandArg(),
):
    """处理接受结婚"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)

    logger.info(f"用户 {user_id} 在群 {group_id} 执行接受结婚命令")

    # 查找所有待处理的请求
    try:
        logger.debug(f"开始获取用户 {user_id} 在群 {group_id} 的待处理请求")
        pending_requests = await marriage_manager.get_pending_requests(
            user_id, group_id
        )
        logger.info(f"找到 {len(pending_requests)} 个待处理求婚请求")

        if not pending_requests:
            return

    except ValueError as e:
        logger.error(f"获取求婚请求失败: {e}", exc_info=True)
        await accept_cmd.finish(f"{e}")
        return
    except Exception as e:
        logger.error(f"获取求婚请求时发生未知错误: {e}", exc_info=True)
        return

    # 获取消息中的at对象
    at_targets = []
    for segment in event.message:
        if segment.type == "at":
            qq = segment.data.get("qq")
            if qq and qq != "all":
                at_targets.append(str(qq))

    logger.debug(f"解析到 {len(at_targets)} 个@目标: {at_targets}")

    selected_request = None

    # 方案1：如果有@某人，接受指定的请求
    if at_targets:
        target_id = at_targets[0]
        logger.info(f"用户选择了通过@指定目标: {target_id}")

        for request in pending_requests:
            if request["proposer_id"] == target_id:
                selected_request = request
                logger.info(
                    f"找到匹配的求婚请求: {request['proposer_name']}({target_id})"
                )
                break

        if not selected_request:
            logger.warning(f"未找到用户 {user_id} 对目标 {target_id} 的求婚请求")
            await accept_cmd.finish("❌ 未找到对应的求婚请求！")
            return

    # 方案2：如果没有@任何人，默认同意第一个
    else:
        selected_request = pending_requests[0]
        logger.info(
            f"用户未指定目标，默认接受第一个请求: {selected_request['proposer_name']}({selected_request['proposer_id']})"
        )

    # 拒绝其他所有请求
    try:
        reject_count = 0
        for request in pending_requests:
            if request["request_id"] != selected_request["request_id"]:
                logger.debug(
                    f"拒绝其他请求: {request['proposer_name']}({request['proposer_id']})"
                )
                await marriage_manager.reject_marriage_request(request["request_id"])
                reject_count += 1

        logger.info(f"成功拒绝了 {reject_count} 个其他求婚请求")

    except Exception as e:
        logger.error(f"拒绝其他请求时发生错误: {e}", exc_info=True)
        await accept_cmd.finish("❌ 处理其他请求时出现错误")
        return

    # 接受选中的请求
    try:
        logger.info(f"开始接受选中的求婚请求: {selected_request['request_id']}")
        success = await marriage_manager.accept_marriage_request(
            selected_request["request_id"]
        )

        if success:
            logger.info(
                f"成功接受求婚请求，求婚者: {selected_request['proposer_name']}, 接受者: {user_id}"
            )
            await send_marriage_success_message(selected_request, event)
        else:
            logger.error(f"接受求婚请求失败，请求ID: {selected_request['request_id']}")
            await accept_cmd.finish("❌ 处理求婚请求时出现错误")

    except Exception as e:
        logger.error(f"接受求婚请求时发生错误: {e}", exc_info=True)
        await accept_cmd.finish("❌ 处理求婚请求时发生未知错误")


async def send_marriage_success_message(
    selected_request: dict, event: GroupMessageEvent
):
    """发送结婚成功消息"""
    # 直接从事件中获取接受者信息
    target_name = event.sender.nickname or f"用户{event.user_id}"

    message = (
        f"🎉 恭喜 {selected_request['proposer_name']} 和 {target_name} 结为夫妻！💕"
    )
    await accept_cmd.send(message)


@reject_cmd.handle()
async def handle_reject(event: GroupMessageEvent):
    """处理拒绝结婚"""
    user_id = str(event.user_id)
    group_id = str(event.group_id)

    # 查找待处理的请求
    pending_request = await marriage_manager.get_pending_request(user_id, group_id)
    if not pending_request:
        return

    # 拒绝请求
    success = await marriage_manager.reject_marriage_request(
        pending_request["request_id"]
    )  # 修复：改为方括号
    if success:
        await reject_cmd.send("💔 结婚请求已被拒绝。")


@check_marriage_cmd.handle()
async def handle_check_marriage(event: Event, session: Session = UniSession()):
    """查看婚姻状态"""
    user_id = str(event.user_id)
    marriages = await marriage_manager.get_user_marriages(user_id)

    if marriages:
        message = [f"💑 你的婚姻关系 ({len(marriages)}段):"]

        for i, marriage in enumerate(marriages, 1):
            # 确定对方是谁
            if marriage["proposer_id"] == user_id:
                partner_name = marriage["target_name"]
                role = "👰 你求婚"
            else:
                partner_name = marriage["proposer_name"]
                role = "💍 你被求婚"

            # 处理结婚时间
            married_at_str = marriage["married_at"]
            try:
                from datetime import datetime

                married_at_dt = datetime.fromisoformat(
                    married_at_str.replace("Z", "+00:00")
                )
                married_time = married_at_dt.strftime("%m-%d %H:%M")
            except:
                married_time = married_at_str.split("T")[0]  # 只显示日期

            message.append(f"{i}. {partner_name} ({role}) - {married_time}")

        await check_marriage_cmd.send("\n".join(message))
    else:
        await check_marriage_cmd.send("💔 你目前是单身状态")


require("nonebot_plugin_apscheduler")


@scheduler.scheduled_job("cron", hour=0, minute=0)
async def daily_reset_job():
    """每日零点清空所有数据"""
    try:
        success = await marriage_manager.daily_reset_all_data()
        if success:
            logger.info("🎯 每日零点：已清空所有结婚数据、请求记录和宝宝记录")
        else:
            logger.error("❌ 每日清空任务执行失败")
    except Exception as e:
        logger.error(f"❌ 每日清空任务异常: {e}")


@scheduler.scheduled_job("interval", minutes=2)
async def expire_check_job():
    """每2分钟检查一次过期请求"""
    try:
        expired_count = await marriage_manager.cleanup_expired_requests()
        if expired_count > 0:
            logger.info(f"🕒 清理了 {expired_count} 个过期的结婚请求")
    except Exception as e:
        logger.error(f"❌ 清理过期请求异常: {e}")


@get_driver().on_shutdown
async def shutdown_scheduler():
    logger.info("正在停止定时任务...")
    try:
        # 检查调度器是否存在且正在运行
        if (
            hasattr(scheduler, "running")
            and scheduler.running
            and hasattr(scheduler, "shutdown")
        ):
            scheduler.shutdown(wait=False)
            logger.info("定时任务已停止")
        else:
            logger.info("定时任务已停止或不存在")
    except Exception as e:
        logger.warning(f"停止定时任务时出现警告: {e}")


having_baby_users = {}


def check_time_restriction(
    allowed_start_hour=21, allowed_end_hour=5, bypass_chance=0.01, command_name="爱爱"
):
    """
    检查时间限制，有概率可以绕过限制

    Args:
        allowed_start_hour: 允许开始的小时 (默认21)
        allowed_end_hour: 允许结束的小时 (默认5)
        bypass_chance: 绕过限制的概率 (默认0.1)
        command_name: 命令名称，用于提示消息

    Returns:
        tuple: (是否允许, 提示消息)
    """
    import datetime
    import random

    # 获取当前时间
    now = datetime.datetime.now()
    current_hour = now.hour

    # 检查是否在允许的时间段内
    if allowed_start_hour <= allowed_end_hour:
        # 正常时间段，如 10点-18点
        in_allowed_time = allowed_start_hour <= current_hour < allowed_end_hour
    else:
        # 跨天时间段，如 21点-5点
        in_allowed_time = (
            allowed_start_hour <= current_hour <= 23
            or 0 <= current_hour < allowed_end_hour
        )

    # 如果在允许时间段内，直接允许
    if in_allowed_time:
        return True, None

    # 不在允许时间段，检查是否有概率绕过
    if random.random() <= bypass_chance:
        return True, ""
    else:
        tips = [
            f"夜深人静的时候才能{command_name}哦~",
            f"现在不是{command_name}的好时机呢，等夜幕降临再来吧~",
            f"请晚上{allowed_start_hour}点至凌晨{allowed_end_hour}点之间再来{command_name}~夜晚才是缠绵的好时光",
            f"虽然现在不是时候，但也许下次运气会更好呢~晚上来试试吧",
            f"{command_name}的时间还没到哦，晚上{allowed_start_hour}点后再来深入交流吧~",
            f"爱爱需要休息，请晚上{allowed_start_hour}点后再来{command_name}~养精蓄锐才能更持久",
            f"夜晚才是{command_name}的最佳时机哦~等天黑了再来吧",
            f"这种私密的事情，当然要在被窝里悄悄进行啦~晚上再来吧",
            f"这种亲密接触，当然要在浪漫的夜晚进行啦~",
        ]
        return False, random.choice(tips)


@have_baby_cmd.handle()
async def handle_have_baby(
    bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()
):
    """处理生宝宝"""

    is_allowed, tip_message = check_time_restriction(
        allowed_start_hour=21,
        allowed_end_hour=5,
        bypass_chance=0.1,
        command_name="爱爱",
    )

    if not is_allowed:
        await have_baby_cmd.finish(tip_message)

    user_id = str(event.user_id)
    group_id = str(event.group_id)

    # 解析@的用户
    at_users = [
        str(seg.data["qq"]) for seg in args if seg.type == "at" and seg.data.get("qq")
    ]

    try:
        # 获取配偶ID
        spouse_id = at_users[0] if at_users else None

        target_pref = await marriage_manager.get_user_preference(spouse_id, group_id)
        if target_pref and target_pref["allow_baby"] is False:
            await marry_cmd.finish(
                f"{target_pref.get('user_name', '对方')}设置了不允许生宝宝"
            )

        if spouse_id:
            # 如果有@对象，检查是否与该对象有婚姻关系
            marriages = await marriage_manager.get_user_marriages(user_id)
            valid_marriage = None
            for marriage in marriages:
                if (
                    marriage["proposer_id"] == spouse_id
                    or marriage["target_id"] == spouse_id
                ):
                    valid_marriage = marriage
                    break

            if not valid_marriage:
                await have_baby_cmd.finish("❌ 你与@的对象没有婚姻关系！")
                return
        else:
            # 没有@时，获取第一个婚姻关系
            marriages = await marriage_manager.get_user_marriages(user_id)
            if not marriages:
                await have_baby_cmd.finish("❌ 你还没有结婚！")
                return
            marriage = marriages[0]
            spouse_id = (
                marriage["target_id"]
                if marriage["proposer_id"] == user_id
                else marriage["proposer_id"]
            )

        baby_manager = marriage_manager.baby_process_manager
        if await baby_manager.is_in_baby_process(user_id, spouse_id):
            remaining_time = await baby_manager.get_remaining_time(user_id, spouse_id)
            remaining_minutes = max(1, int(remaining_time / 60))
            await have_baby_cmd.finish(
                f"❌ 你与对象已经在爱爱中了，请等待 {remaining_minutes} 分钟！"
            )
            return
        # 开始生宝宝过程
        random_duration = random.randint(900, 3600)  # 15-60分钟
        started = await baby_manager.start_baby_process(
            user1_id=user_id,
            user2_id=spouse_id,
            group_id=group_id,
            duration=random_duration,
            bot=bot,
            have_baby_callback=marriage_manager.have_baby_with_spouse,
        )
        if not started:
            await have_baby_cmd.finish("❌ 生宝宝过程已经开始，请勿重复操作！")
            return

        # 发送开始消息
        spouse_name = (
            marriage["target_name"]
            if marriage["proposer_id"] == user_id
            else marriage["proposer_name"]
        )
        start_msg = MessageSegment.text(
            f"正在努力生宝宝中...请等待 {random_duration // 60} 分钟...\n对象: {spouse_name}"
        )
        await have_baby_cmd.send(start_msg)

    except Exception as e:
        logger.error(f"生宝宝命令异常: {e}")


@check_babies_cmd.handle()
async def handle_check_babies(
    event: Event,
    args: Message = CommandArg(),
):
    """查看宝宝记录"""
    user_id = str(event.user_id)
    page = args.extract_plain_text().strip()
    total_babies = await marriage_manager.get_total_babies(user_id)
    records = await marriage_manager.get_baby_records(user_id)
    baby = marriage_manager.baby_process_manager
    if not records:
        await check_babies_cmd.send("你还没有宝宝呢！")
        return

    # 按父母组合合并记录
    merged_records = {}
    for record in records:
        # 使用 to_dict() 方法获取字典数据
        record_dict = record

        # 使用父母双方的ID作为唯一键
        parent1_id = record_dict["parent1_id"]
        parent2_id = record_dict["parent2_id"]
        parent1_name = record_dict["parent1_name"]
        parent2_name = record_dict["parent2_name"]

        # 创建唯一的父母组合键，确保顺序一致
        parent_ids = sorted([parent1_id, parent2_id])  # 按ID排序确保一致
        partner_key = f"{parent_ids[0]}&{parent_ids[1]}"

        if partner_key not in merged_records:
            merged_records[partner_key] = {
                "parent1_name": parent1_name,
                "parent2_name": parent2_name,
                "baby_count": 0,
                "latest_date": record_dict["created_at"],
            }

        merged_records[partner_key]["baby_count"] += record_dict["baby_count"]
        # 更新最新日期
        if record_dict["created_at"] > merged_records[partner_key]["latest_date"]:
            merged_records[partner_key]["latest_date"] = record_dict["created_at"]

    message = [f"👶 你的宝宝们 (共{baby.format_baby_count_symbols(total_babies)}个):"]

    code = None
    if "." in page:
        try:
            page, code = page.split(".")
            page_num = int(code)
            if page_num < 1:
                await check_babies_cmd.finish("页码必须大于0！")
        except Exception:
            await check_babies_cmd.finish(".后面必须跟数字页码！")

    # 设置每页显示数量
    page_size = 5
    total_records = len(merged_records)
    total_pages = (total_records + page_size - 1) // page_size  # 向上取整

    # 处理页码
    if code:
        current_page = page_num
        if current_page > total_pages:
            await check_babies_cmd.finish(
                f"页码 {current_page} 超出范围，总页数只有 {total_pages} 页"
            )
    else:
        current_page = 1

    # 计算分页范围
    start_index = (current_page - 1) * page_size
    end_index = start_index + page_size
    paged_records = dict(list(merged_records.items())[start_index:end_index])

    # 生成消息
    message = [f"👶 你的宝宝们 (共{baby.format_baby_count_symbols(total_babies)}个):"]

    for i, (partner_key, data) in enumerate(paged_records.items(), start_index + 1):
        latest_date = (
            data["latest_date"].split("T")[0]
            if "T" in data["latest_date"]
            else data["latest_date"]
        )
        message.append(
            baby.format_baby_display(
                data["parent1_name"],
                data["parent2_name"],
                data["baby_count"],
                latest_date,
                i,
            )
        )

    # 添加分页信息
    if total_pages > 1:
        message.append(f"\n第 {current_page}/{total_pages} 页")
        message.append(f"共 {total_records} 条记录")
        if current_page < total_pages:
            message.append(f"输入『我的宝宝.{current_page + 1}』查看下一页")

    await check_babies_cmd.send("\n".join(message))


@preference_cmd.handle()
async def handle_preference(event: Event, args: Message = CommandArg()):
    preference = args.extract_plain_text().strip()

    if not preference:
        await preference_cmd.finish(
            "请指定偏好设置：不结婚 / 不生宝宝 / 恢复全部 / 状态"
        )

    user_id = event.get_user_id()
    user_name = event.sender.nickname if event.sender else "未知用户"
    group_id = event.group_id if hasattr(event, "group_id") else "private"

    if preference == "不结婚":
        # 设置不允许结婚
        await marriage_manager.set_user_preference(user_id, user_name, group_id)
        await preference_cmd.finish("已设置：拒绝所有结婚请求")

    elif preference == "不生宝宝":
        # 设置不允许生宝宝
        await marriage_manager.set_user_preference(user_id, user_name, group_id)
        await preference_cmd.finish("已设置：拒绝生宝宝")

    elif preference == "恢复全部":
        # 恢复所有设置
        await marriage_manager.set_user_preference(user_id, user_name, group_id)
        await preference_cmd.finish("已恢复：允许结婚和生宝宝")

    elif preference == "状态":
        # 查看当前状态
        pref = await marriage_manager.get_user_preference(user_id, group_id)
        if pref:
            status = f"当前偏好设置：\n结婚：{'允许' if pref['allow_marriage'] else '拒绝'}\n生宝宝：{'允许' if pref['allow_baby'] else '拒绝'}"
        else:
            status = "当前偏好设置：默认（允许结婚和生宝宝）"
        await preference_cmd.finish(status)

    else:
        await preference_cmd.finish(
            "未知选项，请使用：不结婚 / 不生宝宝 / 恢复全部 / 状态"
        )


@divorce_cmd.handle()
async def handle_marry(
    event: GroupMessageEvent,
    interface: QryItrface = None,
    args: Message = CommandArg(),
):
    """处理离婚请求"""
    # 获取消息中的at对象
    user_id = str(event.user_id)

    # 解析@的用户
    at_targets = [
        str(seg.data["qq"]) for seg in args if seg.type == "at" and seg.data.get("qq")
    ]

    if not at_targets:
        await divorce_cmd.finish("请@你想要离婚的对象！")

    target_id = at_targets[0]
    user_id = str(event.user_id)

    # 检查是否和自己离婚
    if target_id == user_id:
        return

    # 获取用户信息
    members = await interface.get_members(SceneType.GROUP, str(event.group_id))

    user_info = next((m.user for m in members if m.user.id == user_id), None)
    target_info = next((m.user for m in members if m.user.id == target_id), None)

    if not target_info:
        await divorce_cmd.finish("未在群聊中找到指定的用户！请确认@的是正确的群成员。")

    # 获取昵称
    user_name = user_info.nick or user_info.name or "未知用户"
    target_name = target_info.nick or target_info.name or "未知用户"

    # 执行离婚
    success = await marriage_manager.divorce_with_spouse(user_id, target_id)
    if success:
        # 随机选择悲情离婚消息
        divorce_messages = [
            f"爱情终究没抵得过时间，{user_name}和{target_name}离婚了。",
            f"也许分开对彼此都好，{user_name}和{target_name}的离婚手续办完了。",
            f"故事的最后，{user_name}和{target_name}还是说了再见。",
            f"曾经的美好就留在回忆里吧，{user_name}和{target_name}离婚登记已完成。",
            f"不是不爱了，只是路不同了。{user_name}和{target_name}分开了。",
            f"有些人注定只能陪你走一段路，{user_name}和{target_name}离婚手续已办妥。",
            f"感情走到了尽头，{user_name}和{target_name}好聚好散吧。",
            f"从今往后，{user_name}和{target_name}就是最熟悉的陌生人。",
            f"也许放手才是最好的选择，{user_name}和{target_name}离婚了。",
            f"爱情像沙漏，握得越紧流失得越快。{user_name}和{target_name}离婚了。",
            f"没有谁对谁错，只是{user_name}和{target_name}的缘分尽了。",
            f"谢谢你陪我走过这段路，{user_name}对{target_name}说再见了。",
            f"感情这种事，强求不来。{user_name}和{target_name}离婚手续已完成。",
            f"{user_name}和{target_name}都该开始新的生活了，离婚登记办妥。",
            f"有些爱，只能止于唇齿，掩于岁月。{user_name}和{target_name}分开了。",
        ]
        import random

        message = random.choice(divorce_messages)
        await divorce_cmd.finish(message)
    else:
        await divorce_cmd.finish("离婚失败，请稍后再试！")
