import aiohttp
from nonebot_plugin_orm import get_session
from sqlalchemy import func, select, delete, update
from datetime import datetime, timedelta
from typing import List, Optional

from .SessionManager import BabyProcessManager
from .models import BabyRecord, MarriageRequest, Marriage
from nonebot.adapters.onebot.v11 import MessageSegment
from loguru import logger


class MarriageManager:
    def __init__(self):
        # 初始化生宝宝过程管理器
        self.baby_process_manager = BabyProcessManager()

    async def create_marriage_request(
        self,
        proposer_id: str,
        proposer_name: str,
        target_id: str,
        target_name: str,
        group_id: str,
    ) -> str:
        """创建结婚请求"""

        if not await self.can_propose_today(proposer_id):
            raise ValueError("今天已经求过婚了，请明天再试吧！")
        request_id = (
            f"{proposer_id}_{target_id}_{group_id}_{int(datetime.now().timestamp())}"
        )

        session = get_session()
        async with session.begin():
            marriage_request = MarriageRequest(
                request_id=request_id,
                proposer_id=proposer_id,
                proposer_name=proposer_name,
                target_id=target_id,
                target_name=target_name,
                group_id=group_id,
                created_at=datetime.now(),
                status="pending",
            )
            session.add(marriage_request)

        return request_id

    async def get_pending_request(self, target_id: str, group_id: str) -> dict:
        """获取所有待处理的结婚请求"""
        session = get_session()
        async with session.begin():
            stmt = (
                select(MarriageRequest)
                .where(
                    MarriageRequest.target_id == target_id,
                    MarriageRequest.group_id == group_id,
                    MarriageRequest.status == "pending",
                )
                .order_by(MarriageRequest.created_at.desc())
            )

            result = await session.execute(stmt)
            request = result.scalars().first()

            return request.to_dict() if request else None

    async def get_pending_requests(self, target_id: str, group_id: str) -> List[dict]:
        """获取所有待处理的结婚请求，合并同一求婚者的请求（只保留最新的）"""
        session = get_session()
        async with session.begin():
            stmt = (
                select(MarriageRequest)
                .where(
                    MarriageRequest.target_id == target_id,
                    MarriageRequest.group_id == group_id,
                    MarriageRequest.status == "pending",
                )
                .order_by(MarriageRequest.created_at.desc())
            )

            result = await session.execute(stmt)
            requests = result.scalars().all()

            # 合并同一求婚者的请求，只保留每个求婚者的最新请求
            merged_requests = {}
            for req in requests:
                if req.proposer_id not in merged_requests:
                    merged_requests[req.proposer_id] = req.to_dict()

            return list(merged_requests.values())

    async def get_pending_request_by_id(self, request_id: str) -> Optional[dict]:
        """根据ID获取结婚请求"""
        session = get_session()
        async with session.begin():
            stmt = select(MarriageRequest).where(
                MarriageRequest.request_id == request_id,
                MarriageRequest.status == "pending",
            )
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()
            return request.to_dict() if request else None

    async def accept_marriage_request(self, request_id: str) -> bool:
        """接受结婚请求"""
        session = get_session()
        async with session.begin():
            # 获取请求
            stmt = select(MarriageRequest).where(
                MarriageRequest.request_id == request_id,
                MarriageRequest.status == "pending",
            )
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()

            if not request:
                return False

            # 检查双方是否已有婚姻
            # existing_marriage = await self.get_user_marriage(request.proposer_id) or await self.get_user_marriage(request.target_id)
            # if existing_marriage:
            #     # 更新请求状态为拒绝
            #     stmt = update(MarriageRequest).where(
            #         MarriageRequest.request_id == request_id
            #     ).values(status="rejected")
            #     await session.execute(stmt)
            #     return False

            # 创建婚姻记录
            marriage_id = f"marriage_{request.proposer_id}_{request.target_id}"
            marriage = Marriage(
                marriage_id=marriage_id,
                proposer_id=request.proposer_id,
                proposer_name=request.proposer_name,
                target_id=request.target_id,
                target_name=request.target_name,
                group_id=request.group_id,
                married_at=datetime.now(),
                status="married",
            )

            # 更新请求状态
            stmt = (
                update(MarriageRequest)
                .where(MarriageRequest.request_id == request_id)
                .values(status="accepted")
            )
            await session.execute(stmt)

            session.add(marriage)
            return True

    async def reject_marriage_request(self, request_id: str) -> bool:
        """拒绝结婚请求"""
        session = get_session()
        async with session.begin():
            stmt = (
                update(MarriageRequest)
                .where(
                    MarriageRequest.request_id == request_id,
                    MarriageRequest.status == "pending",
                )
                .values(status="rejected")
            )

            result = await session.execute(stmt)
            return result.rowcount > 0

    async def get_user_marriage(self, user_id: str) -> Optional[dict]:
        """获取用户的婚姻关系"""
        session = get_session()
        async with session.begin():
            stmt = select(Marriage).where(
                (Marriage.proposer_id == user_id) | (Marriage.target_id == user_id),
                Marriage.status == "married",
            )
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()
            return request.to_dict() if request else None

    async def get_user_marriages(self, user_id: str) -> List[dict]:
        """获取用户的所有婚姻关系"""
        session = get_session()
        async with session.begin():
            stmt = select(Marriage).where(
                (Marriage.proposer_id == user_id) | (Marriage.target_id == user_id),
                Marriage.status == "married",
            )
            result = await session.execute(stmt)
            marriages = result.scalars().all()
            return [marriage.to_dict() for marriage in marriages]

    async def divorce(self, user_id: str) -> bool:
        """离婚"""
        session = get_session()
        async with session.begin():
            stmt = select(Marriage).where(
                (Marriage.proposer_id == user_id) | (Marriage.target_id == user_id),
                Marriage.status == "married",
            )
            result = await session.execute(stmt)
            marriage = result.scalar_one_or_none()

            if marriage:
                stmt = (
                    update(Marriage)
                    .where(Marriage.marriage_id == marriage.marriage_id)
                    .values(status="divorced")
                )
                await session.execute(stmt)
                return True
            return False

    async def cleanup_expired_requests(self):
        """清理过期的请求"""
        session = get_session()
        async with session.begin():
            expired_time = datetime.now() - timedelta(seconds=120)
            stmt = select(MarriageRequest).where(
                MarriageRequest.status == "pending",
                MarriageRequest.created_at < expired_time,
            )
            result = await session.execute(stmt)
            expired_requests = result.scalars().all()

            for request in expired_requests:
                stmt = (
                    update(MarriageRequest)
                    .where(MarriageRequest.id == request.id)
                    .values(status="expired")
                )
                await session.execute(stmt)

            return len(expired_requests)

    async def daily_reset_all_data(self):
        """每日零点清空所有结婚数据，包括宝宝记录"""
        session = get_session()
        async with session.begin():
            # 删除所有婚姻记录
            stmt_marriages = delete(Marriage)
            await session.execute(stmt_marriages)

            # 删除所有结婚请求记录
            stmt_requests = delete(MarriageRequest)
            await session.execute(stmt_requests)

            logger.info("✅ 每日清空：婚姻记录、请求记录已清空")
            return True

    async def download_avatar_as_image(
        self, avatar_url: str
    ) -> Optional[MessageSegment]:
        """下载头像并转换为图片消息段"""
        if not avatar_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status != 200:
                        return None

                    content = await resp.read()
                    # 检查文件大小（例如限制为15MB）
                    if len(content) > 15 * 1024 * 1024:
                        return None

                    # 创建图片消息段
                    return MessageSegment.image(content)

        except Exception as e:
            logger.error(f"下载头像失败: {e}")
            return None

    async def can_propose_today(self, proposer_id: str) -> bool:
        """检查今天是否已经求过婚"""
        session = get_session()
        async with session.begin():
            # 获取今天的日期范围
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_end = today_start + timedelta(days=1)

            stmt = select(MarriageRequest).where(
                MarriageRequest.proposer_id == proposer_id,
                MarriageRequest.created_at >= today_start,
                MarriageRequest.created_at < today_end,
                MarriageRequest.status.in_(
                    ["pending", "accepted"]
                ),  # 包括待处理和已接受的请求
            )

            result = await session.execute(stmt)
            existing_requests = result.scalars().all()

            # 如果今天已经有求婚记录，返回False
            return len(existing_requests) == 0

    async def have_baby(self, user_id: str, group_id: str, baby_count: int = 1) -> dict:
        """生宝宝"""
        session = get_session()
        async with session.begin():
            # 查找用户的有效婚姻
            stmt = select(Marriage).where(
                (Marriage.proposer_id == user_id) | (Marriage.target_id == user_id),
                Marriage.status == "married",
            )
            result = await session.execute(stmt)
            marriages = result.scalars().all()

            if not marriages:
                raise ValueError("你还没有结婚，不能生宝宝哦！")

            # 使用第一个有效婚姻
            marriage = marriages[0]

            # 确定父母信息
            if marriage.proposer_id == user_id:
                parent1_id = marriage.proposer_id
                parent1_name = marriage.proposer_name
                parent2_id = marriage.target_id
                parent2_name = marriage.target_name
            else:
                parent1_id = marriage.target_id
                parent1_name = marriage.target_name
                parent2_id = marriage.proposer_id
                parent2_name = marriage.proposer_name

            # 创建宝宝记录
            baby_record = BabyRecord(
                marriage_id=marriage.marriage_id,
                parent1_id=parent1_id,
                parent1_name=parent1_name,
                parent2_id=parent2_id,
                parent2_name=parent2_name,
                baby_count=baby_count,
                group_id=group_id,
            )
            session.add(baby_record)

            return {
                "parent1_name": parent1_name,
                "parent2_name": parent2_name,
                "baby_count": baby_count,
                "total_babies": await self.get_total_babies(user_id),
            }

    async def have_baby_with_spouse(
        self, user_id: str, spouse_id: str, group_id: str, baby_count: int = 1
    ) -> dict:
        """与指定配偶生宝宝"""
        session = get_session()
        async with session.begin():
            # 查找与指定配偶的婚姻关系
            stmt = select(Marriage).where(
                (
                    (Marriage.proposer_id == user_id)
                    & (Marriage.target_id == spouse_id)
                    | (Marriage.proposer_id == spouse_id)
                    & (Marriage.target_id == user_id)
                ),
                Marriage.status == "married",
            )
            result = await session.execute(stmt)
            marriage = result.scalar()

            if not marriage:
                raise ValueError("你与指定的用户没有婚姻关系，不能生宝宝哦！")

            # 确定父母信息
            if marriage.proposer_id == user_id:
                parent1_id = marriage.proposer_id
                parent1_name = marriage.proposer_name
                parent2_id = marriage.target_id
                parent2_name = marriage.target_name
            else:
                parent1_id = marriage.target_id
                parent1_name = marriage.target_name
                parent2_id = marriage.proposer_id
                parent2_name = marriage.proposer_name

            # 创建宝宝记录
            baby_record = BabyRecord(
                marriage_id=marriage.marriage_id,
                parent1_id=parent1_id,
                parent1_name=parent1_name,
                parent2_id=parent2_id,
                parent2_name=parent2_name,
                baby_count=baby_count,
                group_id=group_id,
            )
            session.add(baby_record)

            return {
                "parent1_name": parent1_name,
                "parent2_name": parent2_name,
                "baby_count": baby_count,
                "total_babies": await self.get_total_babies(user_id, spouse_id),
            }

    async def get_total_babies(self, user_id: str, spouse_id: str = None) -> int:
        """获取宝宝总数量

        Args:
            user_id: 用户ID
            spouse_id: 伴侣ID（可选）
                - 如果提供：查询这对夫妻共同生育的宝宝总数量
                - 如果不提供：查询该用户所有宝宝数量（包括与不同伴侣生育的）
        """
        session = get_session()
        async with session.begin():
            if spouse_id:
                # 查询这对夫妻共同生育的宝宝总数量
                stmt = select(func.sum(BabyRecord.baby_count)).where(
                    (
                        (BabyRecord.parent1_id == user_id)
                        & (BabyRecord.parent2_id == spouse_id)
                    )
                    | (
                        (BabyRecord.parent1_id == spouse_id)
                        & (BabyRecord.parent2_id == user_id)
                    )
                )
            else:
                # 查询该用户所有宝宝数量（包括与不同伴侣生育的）
                stmt = select(func.sum(BabyRecord.baby_count)).where(
                    (BabyRecord.parent1_id == user_id)
                    | (BabyRecord.parent2_id == user_id)
                )

            result = await session.execute(stmt)
            total = result.scalar() or 0
            return total

    async def get_baby_records(self, user_id: str) -> List[dict]:
        """获取用户的宝宝记录"""
        session = get_session()
        async with session.begin():
            stmt = (
                select(BabyRecord)
                .where(
                    (BabyRecord.parent1_id == user_id)
                    | (BabyRecord.parent2_id == user_id)
                )
                .order_by(BabyRecord.created_at.desc())
            )

            result = await session.execute(stmt)
            records = result.scalars().all()
            return [record.to_dict() for record in records]
