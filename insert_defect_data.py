"""
向缺陷表插入测试数据的脚本
"""
from sqlalchemy.orm import sessionmaker
from models.database import engine, SessionLocal
from models.models import Defect, DefectStatus, DefectPriority, DefectType, DefectSeverity
from datetime import datetime
import json

def insert_defect_data():
    """插入缺陷测试数据"""
    db = SessionLocal()
    try:
        # 准备插入的缺陷数据
        defects_data = [
            {
                "title": "登录页面验证码显示异常",
                "description": "在Chrome浏览器中，登录页面的验证码图片无法正常显示，导致用户无法完成登录操作。",
                "status": DefectStatus.NEW,
                "priority": DefectPriority.HIGH,
                "type": DefectType.UI_BUG,
                "severity": DefectSeverity.MAJOR,
                "project_id": "P209141526675066880",
                "project_name": "项目管理系统",
                "assignee_id": "U209141526675066881",
                "assignee_name": "张三",
                "reporter_id": "U209141526675066882",
                "reporter_name": "李四",
                "version": "v1.0.0",
                "environment": "生产环境",
                "steps_to_reproduce": "1. 打开登录页面\\n2. 输入用户名和密码\\n3. 观察验证码区域",
                "expected_result": "验证码图片正常显示",
                "actual_result": "验证码图片显示为空白或错误图标",
                "tags": json.dumps(["UI", "登录", "验证码"])
            },
            {
                "title": "数据导出功能性能问题",
                "description": "当导出大量数据时，系统响应时间过长，超过30秒，用户体验较差。",
                "status": DefectStatus.ASSIGNED,
                "priority": DefectPriority.MEDIUM,
                "type": DefectType.PERFORMANCE,
                "severity": DefectSeverity.MODERATE,
                "project_id": "P209141526675066880",
                "project_name": "项目管理系统",
                "assignee_id": "U209141526675066881",
                "assignee_name": "王五",
                "reporter_id": "U209141526675066882",
                "reporter_name": "赵六",
                "version": "v1.0.0",
                "environment": "测试环境",
                "steps_to_reproduce": "1. 登录系统\\n2. 进入数据管理页面\\n3. 选择导出全部数据\\n4. 点击导出按钮",
                "expected_result": "数据导出在10秒内完成",
                "actual_result": "数据导出需要30秒以上",
                "tags": json.dumps(["性能", "导出", "优化"])
            },
            {
                "title": "用户权限验证漏洞",
                "description": "普通用户可以通过修改URL参数访问管理员功能，存在权限绕过风险。",
                "status": DefectStatus.IN_PROGRESS,
                "priority": DefectPriority.URGENT,
                "type": DefectType.SECURITY,
                "severity": DefectSeverity.CRITICAL,
                "project_id": "P209141526675066880",
                "project_name": "项目管理系统",
                "assignee_id": "U209141526675066881",
                "assignee_name": "安全专家",
                "reporter_id": "U209141526675066882",
                "reporter_name": "测试工程师",
                "version": "v1.0.0",
                "environment": "生产环境",
                "steps_to_reproduce": "1. 以普通用户身份登录\\n2. 修改URL为管理员页面地址\\n3. 观察是否能访问管理功能",
                "expected_result": "系统拒绝访问并跳转到权限错误页面",
                "actual_result": "可以正常访问管理员功能",
                "tags": json.dumps(["安全", "权限", "漏洞"])
            }
        ]
        
        # 插入数据
        inserted_defects = []
        for defect_data in defects_data:
            defect = Defect(**defect_data)
            db.add(defect)
            db.flush()
            inserted_defects.append(defect)
        
        db.commit()
        
        print("✅ 成功插入缺陷数据！")
        print(f"📊 插入记录数: {len(inserted_defects)}")
        print("\\n📋 插入的缺陷记录:")
        
        for i, defect in enumerate(inserted_defects, 1):
            print(f"\\n{i}. 缺陷ID: {defect.id}")
            print(f"   标题: {defect.title}")
            print(f"   状态: {defect.status.value}")
            print(f"   优先级: {defect.priority.value}")
            print(f"   类型: {defect.type.value}")
            print(f"   严重程度: {defect.severity.value}")
            print(f"   负责人: {defect.assignee_name}")
            print(f"   报告人: {defect.reporter_name}")
            print(f"   创建时间: {defect.created_at}")
        
        return inserted_defects
        
    except Exception as e:
        db.rollback()
        print(f"❌ 插入数据失败: {str(e)}")
        raise e
    finally:
        db.close()

def query_defects():
    """查询所有缺陷数据"""
    db = SessionLocal()
    try:
        defects = db.query(Defect).all()
        
        print(f"\\n📊 数据库中共有 {len(defects)} 条缺陷记录:")
        
        for i, defect in enumerate(defects, 1):
            print(f"\\n{i}. 缺陷ID: {defect.id}")
            print(f"   标题: {defect.title}")
            print(f"   状态: {defect.status.value}")
            print(f"   优先级: {defect.priority.value}")
            print(f"   类型: {defect.type.value}")
            print(f"   严重程度: {defect.severity.value}")
            print(f"   负责人: {defect.assignee_name}")
            print(f"   报告人: {defect.reporter_name}")
            print(f"   创建时间: {defect.created_at}")
            if defect.resolution:
                print(f"   解决方案: {defect.resolution}")
        
        return defects
        
    except Exception as e:
        print(f"❌ 查询数据失败: {str(e)}")
        raise e
    finally:
        db.close()

def main():
    """主函数"""
    print("🚀 开始插入缺陷数据...")
    
    # 插入数据
    insert_defect_data()
    
    print("\\n" + "="*50)
    print("📋 查询所有缺陷数据...")
    
    # 查询数据
    query_defects()
    
    print("\\n✅ 操作完成！")

if __name__ == "__main__":
    main()