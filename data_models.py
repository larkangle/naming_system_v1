from pydantic import BaseModel, Field
from typing import List, Optional

class NameProposal(BaseModel):
    name: str = Field(description="提议的名字（中文全名，包含姓氏）")
    pinyin: str = Field(description="名字的拼音（带声调，如 Lǐ Míng）")
    meaning: str = Field(description="详细寓意说明（至少50字），必须包含：1）每个字的字面含义解析；2）典故出处（如来自哪首诗词、哪部经典）；3）整体文化意象和意境；4）对孩子的美好祝愿和期望")
    proposer: str = Field(description="提案人的角色名称（如：语言学家、诗词专家等）")

class Critique(BaseModel):
    critic_role: str = Field(description="点评专家的角色名称")
    comment: str = Field(description="详细专业点评（至少50字），必须包含：1）从本专业角度的优缺点分析；2）具体的改进建议或肯定理由；3）与用户需求的契合度评价")
    score: int = Field(description="评分（1-10分），10分为最佳，需严格参照评分标准表", ge=1, le=10)

class ScoredName(BaseModel):
    name_info: NameProposal
    critiques: List[Critique] = Field(default_factory=list, description="所有专家对该名字的详细点评列表")
    total_score: int = Field(default=0, description="所有专家评分的总和")
    average_score: float = Field(default=0.0, description="所有专家评分的平均值，保留两位小数")

class FinalReport(BaseModel):
    ranked_names: List[ScoredName] = Field(description="按总分从高到低排序的名字列表，包含前15名")
    summary: str = Field(description="会议总结，必须包含：1）本次会议的讨论过程概述；2）各位专家的主要观点和分歧；3）最终推荐名字的核心理由；4）对家长的温馨建议")
