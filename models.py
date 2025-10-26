from nonebot_plugin_orm import Model
from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime

# 定义数据模型
class MarriageRequest(Model):
    """结婚请求表"""
    __tablename__ = "marriage_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(100), unique=True, nullable=False, index=True)
    proposer_id = Column(String(100), nullable=False, index=True)
    proposer_name = Column(String(100))
    target_id = Column(String(100), nullable=False, index=True)
    target_name = Column(String(100))
    group_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String(20), default="pending")  # pending, accepted, rejected, expired
    
    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "proposer_id": self.proposer_id,
            "proposer_name": self.proposer_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "group_id": self.group_id,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "status": self.status
        }

class Marriage(Model):
    """婚姻关系表"""
    __tablename__ = "marriages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    marriage_id = Column(String(100), unique=True, nullable=False, index=True)
    proposer_id = Column(String(100), nullable=False, index=True)
    proposer_name = Column(String(100))
    target_id = Column(String(100), nullable=False, index=True)
    target_name = Column(String(100))
    group_id = Column(String(100), nullable=False, index=True)
    married_at = Column(DateTime, default=datetime.now)
    status = Column(String(20), default="married")  # married, divorced
    
    def to_dict(self):
        return {
            "id": self.id,
            "marriage_id": self.marriage_id,
            "proposer_id": self.proposer_id,
            "proposer_name": self.proposer_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "group_id": self.group_id,
            "married_at": self.married_at.isoformat() if hasattr(self.married_at, 'isoformat') else self.married_at,
            "status": self.status
        }

class BabyRecord(Model):
    """宝宝记录表"""
    __tablename__ = "baby_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    marriage_id = Column(String(100), nullable=False, index=True)  # 关联的婚姻ID
    parent1_id = Column(String(100), nullable=False, index=True)   # 父母ID1
    parent1_name = Column(String(100))
    parent2_id = Column(String(100), nullable=False, index=True)   # 父母ID2  
    parent2_name = Column(String(100))
    baby_count = Column(Integer, default=1)  # 生的宝宝数量
    created_at = Column(DateTime, default=datetime.now)
    group_id = Column(String(100), nullable=False, index=True)     # 群组ID
    
    def to_dict(self):
        return {
            "id": self.id,
            "marriage_id": self.marriage_id,
            "parent1_id": self.parent1_id,
            "parent1_name": self.parent1_name,
            "parent2_id": self.parent2_id,
            "parent2_name": self.parent2_name,
            "baby_count": self.baby_count,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "group_id": self.group_id
        }