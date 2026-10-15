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

# 默认演示课：与本机「课程」页 COPD 售课一致（封面已进仓库 uploads/courses）
DEMO_COPD_COURSES = [
    (
        "COPD 认识与早期筛查",
        "COPD 系列",
        "了解慢性阻塞性肺疾病的成因、症状与早期筛查要点。",
        2.99,
        "/uploads/courses/copd-screen.svg",
    ),
    (
        "COPD 呼吸康复入门",
        "COPD 系列",
        "呼吸训练、活动耐力与居家康复的基础方法。",
        2.99,
        "/uploads/courses/copd-rehab.svg",
    ),
    (
        "COPD 用药与吸入装置指导",
        "COPD 系列",
        "常用药物类别及吸入装置正确使用要点。",
        2.99,
        "/uploads/courses/copd-meds.svg",
    ),
    (
        "COPD 急性加重自我管理",
        "COPD 系列",
        "识别急性加重信号与就医、用药应对原则。",
        2.99,
        "/uploads/courses/copd-flare.svg",
    ),
    (
        "COPD 家庭氧疗与日常护理",
        "COPD 系列",
        "家庭氧疗注意事项与日常护理、防感染建议。",
        2.99,
        "/uploads/courses/copd-oxygen.svg",
    ),
]

# 旧版校园演示课名（队友若仍是这些，启动时会迁到 COPD）
LEGACY_CAMPUS_COURSE_NAMES = {"高等数学A", "大学英语III", "计算机网络"}


STUDENT_DEMO_AVATAR = "/uploads/avatars/s2024001.jpg"

# 第二个管理员账号（协作演示用），新库和已有库都会补上
EXTRA_ADMIN_USERNAME = "jz12345"
EXTRA_ADMIN_PASSWORD = "12345"


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
    """已有库若无资料/成绩示例则补几条（挂到 COPD 课）。"""
    if db.query(CourseMaterial).first() or db.query(Grade).first():
        return
    teacher = db.query(User).filter(User.username == "t1001").first()
    student = db.query(User).filter(User.username == "s2024001").first()
    c1 = (
        db.query(Course)
        .filter(Course.name == "COPD 认识与早期筛查")
        .first()
        or db.query(Course).order_by(Course.id).first()
    )
    c3 = (
        db.query(Course)
        .filter(Course.name == "COPD 家庭氧疗与日常护理")
        .first()
    )
    if not teacher or not student or not c1:
        return
    db.add_all(
        [
            CourseMaterial(
                course_id=c1.id,
                title="COPD 筛查要点速查",
                url="https://example.com/copd-screen",
                note="对照症状清单做自我评估",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c1.id,
                title="呼吸日记模板",
                url="",
                note="建议连续记录 7 天",
                creator_id=teacher.id,
            ),
        ]
    )
    if c3:
        db.add(
            CourseMaterial(
                course_id=c3.id,
                title="家庭氧疗安全须知",
                url="https://example.com/copd-oxygen",
                note="用氧环境与防火要点",
                creator_id=teacher.id,
            )
        )
    db.add_all(
        [
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="筛查知识自测",
                score=88,
                remark="掌握良好",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="呼吸日记完成度",
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
                title="氧疗安全测验",
                score=92,
                remark="要点齐全",
                creator_id=teacher.id,
            )
        )
    db.commit()


def ensure_copd_courses(db: Session) -> None:
    """
    若仍是旧校园演示课（高等数学等），替换为 COPD 售课，
    让队友 pull 后重启即可看到与主开发者一致的课程页。
    """
    courses = db.query(Course).order_by(Course.id).all()
    if not courses:
        teacher = db.query(User).filter(User.username == "t1001").first()
        tid = teacher.id if teacher else None
        for name, sem, desc, price, cover in DEMO_COPD_COURSES:
            db.add(
                Course(
                    name=name,
                    semester=sem,
                    teacher_id=tid,
                    description=desc,
                    price=price,
                    cover_url=cover,
                )
            )
        db.commit()
        return

    names = {c.name for c in courses}
    has_legacy = bool(names & LEGACY_CAMPUS_COURSE_NAMES)
    has_copd = any(n.startswith("COPD") for n in names)
    if has_copd and not has_legacy:
        # 已是 COPD：补封面 / 标价即可
        changed = False
        by_name = {c.name: c for c in courses}
        for name, sem, desc, price, cover in DEMO_COPD_COURSES:
            c = by_name.get(name)
            if not c:
                continue
            if not (c.cover_url or "").strip():
                c.cover_url = cover
                changed = True
            if not c.price or c.price <= 0:
                c.price = price
                changed = True
            if (c.semester or "").strip() != sem:
                c.semester = sem
                changed = True
        if changed:
            db.commit()
        return
    if not has_legacy:
        return

    # 清空旧课关联后写入 COPD
    from .models import CoursePurchase, ReminderPreference

    rem_ids = [r.id for r in db.query(Reminder).filter(Reminder.course_id.isnot(None)).all()]
    if rem_ids:
        db.query(ReminderPreference).filter(ReminderPreference.reminder_id.in_(rem_ids)).delete(
            synchronize_session=False
        )
        db.query(Reminder).filter(Reminder.id.in_(rem_ids)).delete(synchronize_session=False)
    db.query(ScheduleSlot).delete()
    db.query(CourseMaterial).delete()
    db.query(Grade).delete()
    db.query(Enrollment).delete()
    db.query(CoursePurchase).delete()
    db.query(Course).delete()
    db.commit()

    teacher = db.query(User).filter(User.username == "t1001").first()
    admin = db.query(User).filter(User.role == "admin").first()
    student = db.query(User).filter(User.username == "s2024001").first()
    student2 = db.query(User).filter(User.username == "s2024002").first()
    tid = teacher.id if teacher else (admin.id if admin else None)

    new_courses: list[Course] = []
    for name, sem, desc, price, cover in DEMO_COPD_COURSES:
        c = Course(
            name=name,
            semester=sem,
            teacher_id=tid,
            description=desc,
            price=price,
            cover_url=cover,
        )
        db.add(c)
        new_courses.append(c)
    db.flush()

    if student:
        for c in new_courses:
            db.add(Enrollment(student_id=student.id, course_id=c.id))
    if student2 and new_courses:
        db.add(Enrollment(student_id=student2.id, course_id=new_courses[0].id))
        if len(new_courses) > 1:
            db.add(Enrollment(student_id=student2.id, course_id=new_courses[-1].id))

    now = datetime.utcnow()
    if teacher and new_courses:
        db.add_all(
            [
                Reminder(
                    course_id=new_courses[0].id,
                    title="完成「早期筛查」第一节",
                    content="观看筛查要点视频，并完成症状自测清单。",
                    due_at=now + timedelta(hours=4),
                    external_url="",
                    creator_id=teacher.id,
                    source="system",
                ),
                Reminder(
                    course_id=new_courses[1].id,
                    title="居家呼吸训练打卡",
                    content="完成腹式呼吸练习 10 分钟并记录感受。",
                    due_at=now + timedelta(days=2),
                    external_url="",
                    creator_id=teacher.id,
                    source="system",
                ),
            ]
        )
        db.add_all(
            [
                ScheduleSlot(
                    course_id=new_courses[0].id,
                    weekday=0,
                    start_time="09:00",
                    end_time="09:40",
                    location="线上直播",
                ),
                ScheduleSlot(
                    course_id=new_courses[1].id,
                    weekday=2,
                    start_time="15:00",
                    end_time="15:40",
                    location="线上直播",
                ),
            ]
        )
    db.commit()


def ensure_extra_admin(db: Session) -> None:
    """确保协作演示用的第二个管理员账号（jz12345）存在。"""
    if db.query(User).filter(User.username == EXTRA_ADMIN_USERNAME).first():
        return
    db.add(
        User(
            username=EXTRA_ADMIN_USERNAME,
            password_hash=hash_password(EXTRA_ADMIN_PASSWORD),
            full_name=EXTRA_ADMIN_USERNAME,
            role="admin",
            avatar_url="",
        )
    )
    db.commit()


def seed_if_empty(db: Session) -> None:
    if db.query(User).first():
        ensure_copd_courses(db)
        ensure_demo_avatars(db)
        ensure_demo_urgent_notice(db)
        ensure_demo_materials_grades(db)
        ensure_demo_service_products(db)
        ensure_extra_admin(db)
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

    new_courses: list[Course] = []
    for name, sem, desc, price, cover in DEMO_COPD_COURSES:
        c = Course(
            name=name,
            semester=sem,
            teacher_id=teacher.id,
            description=desc,
            price=price,
            cover_url=cover,
        )
        db.add(c)
        new_courses.append(c)
    db.flush()
    c1, c2, c3 = new_courses[0], new_courses[1], new_courses[-1]

    db.add_all(
        [
            Enrollment(student_id=student.id, course_id=c.id)
            for c in new_courses
        ]
        + [
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
                title="完成「早期筛查」第一节",
                content="观看筛查要点视频，并完成症状自测清单。",
                due_at=now + timedelta(hours=4),
                external_url="",
                creator_id=teacher.id,
                source="system",
            ),
            Reminder(
                course_id=c2.id,
                title="居家呼吸训练打卡",
                content="完成腹式呼吸练习 10 分钟并记录感受。",
                due_at=now + timedelta(days=2),
                external_url="",
                creator_id=teacher.id,
                source="system",
            ),
            Reminder(
                course_id=c3.id,
                title="家庭氧疗安全复习",
                content="阅读氧疗安全须知，完成课后小测。",
                due_at=now + timedelta(hours=30),
                external_url="",
                creator_id=teacher.id,
                source="system",
            ),
        ]
    )

    db.add_all(
        [
            ScheduleSlot(
                course_id=c1.id, weekday=0, start_time="09:00", end_time="09:40", location="线上直播"
            ),
            ScheduleSlot(
                course_id=c2.id, weekday=2, start_time="15:00", end_time="15:40", location="线上直播"
            ),
            ScheduleSlot(
                course_id=c3.id, weekday=4, start_time="19:00", end_time="19:40", location="线上直播"
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
                content="刚学完早期筛查一课，有人一起打卡呼吸日记吗？",
            ),
            CommunityPost(
                author_id=teacher.id,
                content="本周四晚 19:00 线上答疑：吸入装置常见误区，欢迎带问题来。",
            ),
            CommunityPost(
                author_id=admin.id,
                content="商城新增「急性加重绿色通道咨询」，需要时可在服务页下单。",
            ),
        ]
    )

    db.add_all(
        [
            CourseMaterial(
                course_id=c1.id,
                title="COPD 筛查要点速查",
                url="https://example.com/copd-screen",
                note="对照症状清单做自我评估",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c1.id,
                title="呼吸日记模板",
                url="",
                note="建议连续记录 7 天",
                creator_id=teacher.id,
            ),
            CourseMaterial(
                course_id=c3.id,
                title="家庭氧疗安全须知",
                url="https://example.com/copd-oxygen",
                note="用氧环境与防火要点",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="筛查知识自测",
                score=88,
                remark="掌握良好",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c1.id,
                student_id=student.id,
                title="呼吸日记完成度",
                score=79.5,
                remark="",
                creator_id=teacher.id,
            ),
            Grade(
                course_id=c3.id,
                student_id=student.id,
                title="氧疗安全测验",
                score=92,
                remark="要点齐全",
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
    ensure_extra_admin(db)
