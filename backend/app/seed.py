from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    CalendarEvent,
    CommunityPost,
    Course,
    CourseMaterial,
    Enrollment,
    Grade,
    Notice,
    Reminder,
    ScheduleSlot,
    ServiceProduct,
    User,
)

DEMO_SERVICE_PRODUCTS = [
    (
        "COPD 远程随访咨询",
        "健康服务",
        "医护远程随访一次，复核症状与用药依从性。",
        9.9,
        "单次",
    ),
    (
        "居家呼吸康复指导",
        "健康服务",
        "一对一呼吸训练与活动耐力指导（含复诊建议）。",
        19.9,
        "单次",
    ),
    (
        "吸入装置使用教学",
        "健康服务",
        "视频/远程演示吸入装置正确操作与常见误区纠正。",
        12.9,
        "单次",
    ),
    (
        "用药依从性托管",
        "健康服务",
        "按日提醒用药与记录，月度简报反馈给本人或家属。",
        5.9,
        "30天",
    ),
    (
        "急性加重绿色通道咨询",
        "健康服务",
        "识别加重信号后的就医路径与应急处置建议。",
        29.9,
        "单次",
    ),
]


STUDENT_DEMO_AVATAR = "/uploads/avatars/s2024001.jpg"


def ensure_demo_avatars(db: Session) -> None:
    """保证演示学生已挂上头像（已有库也会补）。"""
    student = db.query(User).filter(User.username == "s2024001").first()
    if student and not student.avatar_url:
        student.avatar_url = STUDENT_DEMO_AVATAR
        db.commit()


def ensure_demo_urgent_notice(db: Session) -> None:
    """已有库若无紧急公告，给一条网络维护标紧急。"""
    if db.query(Notice).filter(Notice.is_urgent.is_(True)).first():
        return
    n = db.query(Notice).filter(Notice.title.contains("网络维护")).first()
    if n:
        n.is_urgent = True
        db.commit()


def ensure_demo_service_products(db: Session) -> None:
    """已有库若无商城服务商品则补 COPD 相关售卖服务。"""
    if db.query(ServiceProduct).first():
        return
    for name, category, desc, price, unit in DEMO_SERVICE_PRODUCTS:
        db.add(
            ServiceProduct(
                name=name,
                category=category,
                description=desc,
                price=price,
                unit_label=unit,
                cover_url="",
            )
        )
    db.commit()


def ensure_demo_materials_grades(db: Session) -> None:
    """已有库若无资料/成绩示例则补几条。"""
    if db.query(CourseMaterial).first() or db.query(Grade).first():
        return
    teacher = db.query(User).filter(User.username == "t1001").first()
    student = db.query(User).filter(User.username == "s2024001").first()
    c1 = db.query(Course).filter(Course.name == "高等数学A").first()
    c3 = db.query(Course).filter(Course.name == "计算机网络").first()
    if not teacher or not student or not c1:
        return
    db.add_all(
        [
            CourseMaterial(
                course_id=c1.id,
                title="第1–4章课件（网盘）",
                url="https://example.com/math-slides",
                note="请在本周五前下载复习",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c1.id,
                title="习题答案（参考）",
                url="",
                note="仅核对思路，勿直接抄录",
                creator_id=teacher.id,
            ),
        ]
    )
    if c3:
        db.add(
            CourseMaterial(
                course_id=c3.id,
                title="Wireshark 实验指南",
                url="https://example.com/net-lab",
                note="实验报告模板见附件链接",
                creator_id=teacher.id,
            )
        )
    db.add_all(
        [
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="平时作业",
                score=88,
                remark="按时提交",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="期中测验",
                score=79.5,
                remark="",
                creator_id=teacher.id,
            ),
        ]
    )
    if c3:
        db.add(
            Grade(
                course_id=c3.id,
                student_id=student.id,
                title="实验一",
                score=92,
                remark="抓包分析完整",
                creator_id=teacher.id,
            )
        )
    db.commit()


def seed_if_empty(db: Session) -> None:
    if db.query(User).first():
        ensure_demo_avatars(db)
        ensure_demo_urgent_notice(db)
        ensure_demo_materials_grades(db)
        ensure_demo_service_products(db)
        return

    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        full_name="系统管理员",
        role="admin",
        avatar_url="",
    )
    teacher = User(
        username="t1001",
        password_hash=hash_password("teach123"),
        full_name="张老师",
        role="teacher",
        avatar_url="",
    )
    student = User(
        username="s2024001",
        password_hash=hash_password("stu123"),
        full_name="李同学",
        role="student",
        avatar_url=STUDENT_DEMO_AVATAR,
    )
    student2 = User(
        username="s2024002",
        password_hash=hash_password("stu123"),
        full_name="王同学",
        role="student",
        avatar_url="",
    )
    db.add_all([admin, teacher, student, student2])
    db.flush()

    c1 = Course(
        name="高等数学A",
        semester="2025-2026-1",
        teacher_id=teacher.id,
        description="微积分与线性代数基础",
    )
    c2 = Course(
        name="大学英语III",
        semester="2025-2026-1",
        teacher_id=teacher.id,
        description="学术英语听说读写",
    )
    c3 = Course(
        name="计算机网络",
        semester="2025-2026-1",
        teacher_id=teacher.id,
        description="网络协议与实践",
    )
    db.add_all([c1, c2, c3])
    db.flush()

    db.add_all(
        [
            Enrollment(student_id=student.id, course_id=c1.id),
            Enrollment(student_id=student.id, course_id=c2.id),
            Enrollment(student_id=student.id, course_id=c3.id),
            Enrollment(student_id=student2.id, course_id=c1.id),
            Enrollment(student_id=student2.id, course_id=c3.id),
        ]
    )

    now = datetime.utcnow()
    db.add_all(
        [
            Notice(
                title="本学期选课补选通知",
                body="补选通道将于本周五 17:00 关闭，请未完成选课的同学尽快登录教务系统办理。",
                audience="student",
                author_id=admin.id,
            ),
            Notice(
                title="期中教学检查安排",
                body="各教学单位请于下周提交期中教学检查材料，具体要求见教务处通知附件说明。",
                audience="teacher",
                author_id=admin.id,
            ),
            Notice(
                title="校园网络维护公告",
                body="本周六 02:00–06:00 进行核心交换机升级，届时校内网可能短暂中断。",
                audience="all",
                is_urgent=True,
                author_id=admin.id,
            ),
        ]
    )

    db.add_all(
        [
            Reminder(
                course_id=c1.id,
                title="第5周网课：极限与连续",
                content="请在学校网课平台完成第5周视频（约90分钟）并提交章节自测。",
                due_at=now + timedelta(hours=4),
                external_url="https://example.edu/mooc/math-a/week5",
                creator_id=teacher.id,
                source="system",
            ),
            Reminder(
                course_id=c2.id,
                title="Unit 3 Listening 任务",
                content="完成 Unit 3 Listening 练习 1–4，并阅读配套材料第 42–48 页。",
                due_at=now + timedelta(days=2),
                external_url="https://example.edu/mooc/english3/unit3",
                creator_id=teacher.id,
                source="system",
            ),
            Reminder(
                course_id=c3.id,
                title="TCP 章节预习",
                content="观看「可靠传输」两节录播，并对照教材第 6 章做笔记。",
                due_at=now + timedelta(hours=30),
                external_url="https://example.edu/mooc/network/tcp",
                creator_id=teacher.id,
                source="system",
            ),
        ]
    )

    db.add_all(
        [
            ScheduleSlot(
                course_id=c1.id, weekday=0, start_time="08:00", end_time="09:40", location="教1-301"
            ),
            ScheduleSlot(
                course_id=c1.id, weekday=2, start_time="10:00", end_time="11:40", location="教1-301"
            ),
            ScheduleSlot(
                course_id=c2.id, weekday=1, start_time="14:00", end_time="15:40", location="外语楼-205"
            ),
            ScheduleSlot(
                course_id=c3.id, weekday=3, start_time="08:00", end_time="09:40", location="实验楼-B201"
            ),
            ScheduleSlot(
                course_id=c3.id, weekday=4, start_time="16:00", end_time="17:40", location="实验楼-B201"
            ),
        ]
    )

    today = date.today()
    db.add_all(
        [
            CalendarEvent(
                title="开学典礼",
                event_date=today - timedelta(days=14),
                description="新学期开学",
            ),
            CalendarEvent(
                title="期中考试周开始",
                event_date=today + timedelta(days=21),
                description="各课程按院系安排考试",
            ),
            CalendarEvent(
                title="国庆放假",
                event_date=today + timedelta(days=40),
                description="具体调休以学校通知为准",
            ),
        ]
    )

    db.add_all(
        [
            CommunityPost(
                author_id=student.id,
                content="有人一起组队参加下周的院系编程马拉松吗？时间灵活，欢迎大一到大三～",
            ),
            CommunityPost(
                author_id=teacher.id,
                content="高数答疑室本周四晚 19:00 在教1-201，带着问题来就好。",
            ),
            CommunityPost(
                author_id=admin.id,
                content="图书馆东区自习室本周末开放延时，周五至周日开放至 23:00。",
            ),
        ]
    )

    db.add_all(
        [
            CourseMaterial(
                course_id=c1.id,
                title="第1–4章课件（网盘）",
                url="https://example.com/math-slides",
                note="请在本周五前下载复习",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c1.id,
                title="习题答案（参考）",
                url="",
                note="仅核对思路，勿直接抄录",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c3.id,
                title="Wireshark 实验指南",
                url="https://example.com/net-lab",
                note="实验报告模板见附件链接",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="平时作业",
                score=88,
                remark="按时提交",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="期中测验",
                score=79.5,
                remark="",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c3.id,
                student_id=student.id,
                title="实验一",
                score=92,
                remark="抓包分析完整",
                creator_id=teacher.id,
            ),
        ]
    )

    for name, category, desc, price, unit in DEMO_SERVICE_PRODUCTS:
        db.add(
            ServiceProduct(
                name=name,
                category=category,
                description=desc,
                price=price,
                unit_label=unit,
                cover_url="",
            )
        )

    db.commit()
