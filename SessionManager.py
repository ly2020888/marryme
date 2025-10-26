import random
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Tuple
from nonebot_plugin_apscheduler import scheduler
from loguru import logger
from nonebot.adapters.onebot.v11 import MessageSegment


class BabyProcessManager:
    """简洁的生宝宝过程管理器"""

    def __init__(self):
        # 使用排序后的夫妻ID作为键
        self.baby_processes: Dict[Tuple[str, str], dict] = {}
        self._lock = asyncio.Lock()

    def _get_process_key(self, user1_id: str, user2_id: str) -> Tuple[str, str]:
        """生成统一的进程键"""
        sorted_ids = sorted([user1_id, user2_id])
        return (sorted_ids[0], sorted_ids[1])

    async def start_baby_process(
        self,
        user1_id: str,
        user2_id: str,
        group_id: str,
        duration: int,
        bot,  # bot实例
        have_baby_callback,  # 生宝宝回调函数
    ) -> bool:
        """开始生宝宝过程

        Returns:
            bool: 是否成功开始
        """
        async with self._lock:
            process_key = self._get_process_key(user1_id, user2_id)

            # 检查是否已存在
            if process_key in self.baby_processes:
                return False

            # 记录过程信息
            self.baby_processes[process_key] = {
                "user1_id": user1_id,
                "user2_id": user2_id,
                "group_id": group_id,
                "start_time": time.time(),
                "duration": duration,  # 保存持续时间
                "bot": bot,
                "have_baby_callback": have_baby_callback,
            }

            # 创建定时任务
            scheduler.add_job(
                self._complete_baby_process,
                "date",
                run_date=datetime.now() + timedelta(seconds=duration),
                id=f"baby_{process_key[0]}_{process_key[1]}",
                args=[user1_id, user2_id],
            )

            logger.info(
                f"开始生宝宝过程: {user1_id} & {user2_id}, 持续时间: {duration}秒"
            )
            return True

    async def _complete_baby_process(self, user1_id: str, user2_id: str):
        """定时任务回调：完成生宝宝过程"""
        process_key = self._get_process_key(user1_id, user2_id)

        async with self._lock:
            process = self.baby_processes.pop(process_key, None)
            if not process:
                return

        try:
            bot = process["bot"]
            have_baby_callback = process["have_baby_callback"]
            group_id = process["group_id"]

            # 生宝宝逻辑
            baby_count = self._realistic_baby_count()
            result = await have_baby_callback(user1_id, user2_id, group_id, baby_count)

            # 构建消息
            total_after_birth = result["total_babies"] + baby_count
            count_display = self.format_baby_count_symbols(total_after_birth)

            if baby_count == 0:
                msg = random.choice(
                    [
                        "😔 很遗憾，这次没有怀上宝宝。",
                        "💔 这次没有成功怀上宝宝，再接再厉！",
                        "🌙 没有怀上宝宝，再多做几次试试也许就能怀上了。",
                    ]
                )
            else:
                msg = (
                    random.choice(
                        [
                            f"🎉 恭喜！喜得{baby_count}个宝宝！👶",
                            f"💕 大喜事！爱情结晶 - {baby_count}个宝宝诞生啦！",
                            f"👶 好消息！家庭新增了{baby_count}个成员！",
                            f"🎊 {baby_count}个宝宝来到这个世界啦！",
                            f"💖 爱情的见证！迎来了{baby_count}个可爱的宝宝！",
                        ]
                    )
                    + f"\n🏠 你们现在共有 {count_display} 个宝宝了！"
                )

            # 发送消息
            result_msg = (
                MessageSegment.text(msg)
                + MessageSegment.at(user1_id)
                + MessageSegment.at(user2_id)
            )
            await bot.send_group_msg(group_id=int(group_id), message=result_msg)

            logger.info(f"生宝宝完成: {user1_id} & {user2_id}, 宝宝数量: {baby_count}")

        except Exception as e:
            logger.error(f"生宝宝过程异常: {e}")

    def _realistic_baby_count(self) -> int:
        """
        基于真实多胞胎概率：
        """
        prob = random.random()
        if prob < 0.5:  # 0-0.5: 50% 单胎
            return 0
        elif prob < 0.8:  # 0.5-0.8: 30% 双胞胎
            return 1
        elif prob < 0.9:  # 0.8-0.9: 10% 三胞胎
            return 2
        elif prob < 0.95:  # 0.9-0.95: 5% 四胞胎
            return 3
        else:  # 0.95-1.0: 5% 五胞胎
            return 4

    async def is_in_baby_process(self, user1_id: str, user2_id: str) -> bool:
        """检查是否在生宝宝过程中"""
        process_key = self._get_process_key(user1_id, user2_id)
        return process_key in self.baby_processes

    async def get_remaining_time(self, user1_id: str, user2_id: str) -> float:
        """获取预估剩余时间（秒）"""
        process_key = self._get_process_key(user1_id, user2_id)
        process = self.baby_processes.get(process_key)
        if not process:
            return 0

        # 根据开始时间计算预估剩余时间
        elapsed = time.time() - process["start_time"]
        # 这里需要存储duration，修改start_baby_process时保存duration
        duration = process.get("duration", 0)
        remaining = duration - elapsed
        return max(0, remaining)

    def format_baby_count_symbols(self, baby_count: int) -> str:
        """将宝宝数量转换为符号显示字符串

        Args:
            baby_count: 宝宝数量

        Returns:
            符号格式的字符串，如：👑x1 ☀️x2 🌙x3 🌟x4
        """
        parts = []

        # 计算各个等级的数量
        crowns = baby_count // 1000
        suns = (baby_count % 1000) // 100
        moons = (baby_count % 100) // 10
        stars = baby_count % 10

        # 按等级添加符号
        if crowns > 0:
            parts.append(f"👑x{crowns}")
        if suns > 0:
            parts.append(f"☀️x{suns}")
        if moons > 0:
            parts.append(f"🌙x{moons}")
        if stars > 0:
            parts.append(f"🌟x{stars}")

        # 如果没有宝宝，显示0个星星
        if not parts:
            parts.append("🌟x0")

        return "".join(parts)

    def format_baby_display(
        self,
        parent1_name: str,
        parent2_name: str,
        baby_count: int,
        date: str,
        index: int = None,
    ) -> str:
        """格式化宝宝信息显示"""

        # 使用已有的符号格式化函数
        count_display = self.format_baby_count_symbols(baby_count)

        # 构建完整字符串
        if index is not None:
            return f"{index}. {parent1_name} 和 {parent2_name} 的宝宝 {count_display} - {date}"
        else:
            return f"{parent1_name} 和 {parent2_name} 的宝宝 {count_display} - {date}"

    async def cleanup(self):
        """清理所有任务"""
        async with self._lock:
            for process_key in list(self.baby_processes.keys()):
                task_id = f"baby_{process_key[0]}_{process_key[1]}"
                try:
                    scheduler.remove_job(task_id)
                except Exception:
                    pass
            self.baby_processes.clear()
