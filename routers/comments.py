"""评论相关的API路由
提供评论的增删改查功能
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from models import get_db, Comment, User, CommentTargetType
from schemas.comment import (
    CommentCreate, CommentUpdate, CommentResponse, CommentListResponse
)
from utils.auth import get_current_user
from utils.permissions import check_permission
import math

router = APIRouter(prefix="/comments")


@router.post("/add", response_model=CommentResponse, summary="创建评论")
async def create_comment(
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新评论"""
    # 验证目标是否存在
    await _validate_target_exists(db, comment_data.target_type, comment_data.target_id)
    
    # 如果是回复评论，验证父评论是否存在
    if comment_data.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == comment_data.parent_id).first()
        if not parent_comment:
            raise HTTPException(status_code=404, detail="父评论不存在")
        if parent_comment.target_type != comment_data.target_type or parent_comment.target_id != comment_data.target_id:
            raise HTTPException(status_code=400, detail="回复评论必须在同一目标下")
    
    # 创建评论
    comment = Comment(
        content=comment_data.content,
        target_type=comment_data.target_type,
        target_id=comment_data.target_id,
        author_id=current_user.id,
        parent_id=comment_data.parent_id
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    # 加载关联数据
    comment = db.query(Comment).options(
        joinedload(Comment.author),
        joinedload(Comment.replies).joinedload(Comment.author)
    ).filter(Comment.id == comment.id).first()
    
    return comment


@router.get("/commentlist", response_model=CommentListResponse, summary="获取评论列表")
async def get_comments(
    target_type: Optional[CommentTargetType] = Query(None, description="目标类型"),
    target_id: Optional[str] = Query(None, description="目标ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取评论列表"""
    # 构建查询条件
    query = db.query(Comment).options(
        joinedload(Comment.author),
        joinedload(Comment.replies).joinedload(Comment.author)
    )
    
    # 只查询顶级评论（非回复）
    query = query.filter(Comment.parent_id.is_(None))
    
    if target_type and target_id:
        query = query.filter(
            and_(Comment.target_type == target_type, Comment.target_id == target_id)
        )
    elif target_type:
        query = query.filter(Comment.target_type == target_type)
    elif target_id:
        query = query.filter(Comment.target_id == target_id)
    
    # 按创建时间倒序排列
    query = query.order_by(Comment.created_at.desc())
    
    # 计算总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * size
    comments = query.offset(offset).limit(size).all()
    
    # 计算总页数
    pages = math.ceil(total / size) if total > 0 else 1
    
    return CommentListResponse(
        comments=comments,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{comment_id}", response_model=CommentResponse, summary="获取评论详情")
async def get_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取评论详情"""
    comment = db.query(Comment).options(
        joinedload(Comment.author),
        joinedload(Comment.replies).joinedload(Comment.author)
    ).filter(Comment.id == comment_id).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    return comment


@router.put("/{comment_id}", response_model=CommentResponse, summary="更新评论")
async def update_comment(
    comment_id: str,
    comment_data: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新评论"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    # 只有评论作者或管理员可以修改评论
    if comment.author_id != current_user.id and not check_permission(current_user, "comment:update"):
        raise HTTPException(status_code=403, detail="没有权限修改此评论")
    
    # 更新评论内容
    if comment_data.content is not None:
        comment.content = comment_data.content
    
    db.commit()
    db.refresh(comment)
    
    # 加载关联数据
    comment = db.query(Comment).options(
        joinedload(Comment.author),
        joinedload(Comment.replies).joinedload(Comment.author)
    ).filter(Comment.id == comment.id).first()
    
    return comment


@router.delete("/{comment_id}", summary="删除评论")
async def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除评论"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    # 只有评论作者或管理员可以删除评论
    if comment.author_id != current_user.id and not check_permission(current_user, "comment:delete"):
        raise HTTPException(status_code=403, detail="没有权限删除此评论")
    
    db.delete(comment)
    db.commit()
    
    return {"message": "评论删除成功"}


async def _validate_target_exists(db: Session, target_type: CommentTargetType, target_id: str):
    """验证评论目标是否存在"""
    if target_type == CommentTargetType.DEFECT:
        from models.defect import Defect
        target = db.query(Defect).filter(Defect.id == target_id).first()
    elif target_type == CommentTargetType.TASK:
        from models.task import Task
        target = db.query(Task).filter(Task.id == target_id).first()
    elif target_type == CommentTargetType.PROJECT:
        from models.project import Project
        target = db.query(Project).filter(Project.id == target_id).first()
    else:
        raise HTTPException(status_code=400, detail="不支持的目标类型")
    
    if not target:
        raise HTTPException(status_code=404, detail=f"{target_type.value}不存在")