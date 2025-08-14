"""MinIO客户端工具模块

提供文件上传、下载、删除等功能
"""
import os
import hashlib
import mimetypes
from typing import Optional, BinaryIO, Tuple
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()


class MinIOClient:
    """MinIO客户端封装类"""
    
    def __init__(self):
        """初始化MinIO客户端"""
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.default_bucket = os.getenv("MINIO_DEFAULT_BUCKET", "documents")
        
        # 创建MinIO客户端
        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # 确保默认存储桶存在
        self._ensure_bucket_exists(self.default_bucket)
    
    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                print(f"✅ 创建MinIO存储桶: {bucket_name}")
        except S3Error as e:
            print(f"❌ MinIO存储桶操作失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"存储服务初始化失败: {str(e)}"
            )
    
    def upload_file(
        self,
        file_data: BinaryIO,
        object_key: str,
        file_size: int,
        content_type: Optional[str] = None,
        bucket_name: Optional[str] = None
    ) -> Tuple[str, str]:
        """上传文件到MinIO
        
        Args:
            file_data: 文件数据流
            object_key: 对象键（文件路径）
            file_size: 文件大小
            content_type: 内容类型
            bucket_name: 存储桶名称
            
        Returns:
            Tuple[bucket_name, object_key]: 存储桶名称和对象键
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            # 确保存储桶存在
            self._ensure_bucket_exists(bucket_name)
            
            # 上传文件
            result = self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_key,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            
            return bucket_name, object_key
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文件上传失败: {str(e)}"
            )
    
    def download_file(
        self,
        object_key: str,
        bucket_name: Optional[str] = None
    ) -> BinaryIO:
        """从MinIO下载文件
        
        Args:
            object_key: 对象键
            bucket_name: 存储桶名称
            
        Returns:
            文件数据流
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            response = self.client.get_object(bucket_name, object_key)
            return response
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文件下载失败: {str(e)}"
            )
    
    def delete_file(
        self,
        object_key: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """删除MinIO中的文件
        
        Args:
            object_key: 对象键
            bucket_name: 存储桶名称
            
        Returns:
            是否删除成功
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            self.client.remove_object(bucket_name, object_key)
            return True
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                # 文件不存在，认为删除成功
                return True
            print(f"⚠️ 删除文件失败: {e}")
            return False
    
    def get_file_url(
        self,
        object_key: str,
        bucket_name: Optional[str] = None,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """获取文件的预签名URL
        
        Args:
            object_key: 对象键
            bucket_name: 存储桶名称
            expires: 过期时间
            
        Returns:
            预签名URL
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_key,
                expires=expires
            )
            return url
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取文件URL失败: {str(e)}"
            )
    
    def file_exists(
        self,
        object_key: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """检查文件是否存在
        
        Args:
            object_key: 对象键
            bucket_name: 存储桶名称
            
        Returns:
            文件是否存在
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            self.client.stat_object(bucket_name, object_key)
            return True
        except S3Error:
            return False
    
    def get_file_info(
        self,
        object_key: str,
        bucket_name: Optional[str] = None
    ) -> dict:
        """获取文件信息
        
        Args:
            object_key: 对象键
            bucket_name: 存储桶名称
            
        Returns:
            文件信息字典
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        
        try:
            stat = self.client.stat_object(bucket_name, object_key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取文件信息失败: {str(e)}"
            )


def calculate_file_checksum(file_data: bytes) -> str:
    """计算文件MD5校验和
    
    Args:
        file_data: 文件数据
        
    Returns:
        MD5校验和
    """
    return hashlib.md5(file_data).hexdigest()


def get_file_type_from_filename(filename: str) -> Tuple[str, str]:
    """从文件名获取文件类型和MIME类型
    
    Args:
        filename: 文件名
        
    Returns:
        Tuple[file_extension, mime_type]: 文件扩展名和MIME类型
    """
    file_ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type is None:
        mime_type = "application/octet-stream"
    
    return file_ext, mime_type


def generate_object_key(filename: str, user_id: str, folder_path: str = "") -> str:
    """生成MinIO对象键
    
    Args:
        filename: 文件名
        user_id: 用户ID
        folder_path: 文件夹路径
        
    Returns:
        对象键
    """
    import uuid
    from datetime import datetime
    
    # 生成唯一文件名
    file_ext = os.path.splitext(filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    
    # 构建对象键
    if folder_path:
        object_key = f"{user_id}/{folder_path}/{unique_filename}"
    else:
        object_key = f"{user_id}/{unique_filename}"
    
    return object_key


# 全局MinIO客户端实例
_minio_client: Optional[MinIOClient] = None


def get_minio_client() -> MinIOClient:
    """获取MinIO客户端实例"""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinIOClient()
    return _minio_client