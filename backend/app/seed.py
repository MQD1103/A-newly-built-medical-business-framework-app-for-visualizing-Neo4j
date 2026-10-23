from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    CalendarEvent,
    CommunityPost,
    Course,
    CourseBundleItem,
    CourseMaterial,
    CourseOrderSeat,
    CoursePurchase,
    Enrollment,
    Grade,
    HospitalPartner,
    Lesson,
    LessonProgress,
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
    from .models import ReminderPreference

    rem_ids = [r.id for r in db.query(Reminder).filter(Reminder.course_id.isnot(None)).all()]
    if rem_ids:
        db.query(ReminderPreference).filter(ReminderPreference.reminder_id.in_(rem_ids)).delete(
            synchronize_session=False
        )
        db.query(Reminder).filter(Reminder.id.in_(rem_ids)).delete(synchronize_session=False)
    db.query(ScheduleSlot).delete()
    db.query(CourseMaterial).delete()
    db.query(Grade).delete()
    db.query(LessonProgress).delete()
    db.query(Lesson).delete()
    db.query(CourseOrderSeat).delete()
    db.query(CourseBundleItem).delete()
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


# ---------- 商城目录 ----------

COPD_PATH_LABELS = {
    "COPD 认识与早期筛查": "预防与预测",
    "COPD 呼吸康复入门": "预防与预测",
    "COPD 用药与吸入装置指导": "患病管理",
    "COPD 急性加重自我管理": "患病管理",
    "COPD 家庭氧疗与日常护理": "患病管理",
}

COPD_TAGLINES = {
    "COPD 认识与早期筛查": "先弄清 COPD 是什么、自己有没有风险",
    "COPD 呼吸康复入门": "呼吸训练与居家康复的基础方法",
    "COPD 用药与吸入装置指导": "把药吸对：常用药物与装置操作",
    "COPD 急性加重自我管理": "识别加重信号，知道何时就医",
    "COPD 家庭氧疗与日常护理": "家庭氧疗安全与日常照护要点",
}

SERVICE_TAGLINES = {
    "COPD 远程随访咨询": "医护远程随访，复核症状与用药依从性",
    "居家呼吸康复指导": "一对一呼吸训练与活动耐力指导",
    "吸入装置使用教学": "纠正漏按、吸气过快等常见错误",
    "用药依从性托管": "按日提醒并记录，月度简报反馈",
    "急性加重绿色通道咨询": "出现加重信号时的就医路径咨询",
}

INTRO_COURSE_NAME = "COPD 免费入门课：这门课能帮你做什么"
BUNDLE_COURSE_NAME = "COPD 系统课（整包）"

# 演示视频由 backend/scripts/generate_demo_videos.py 本地生成或从开源片源裁剪；
# 文件不进仓库。默认 10 秒，需与脚本 --seconds 保持一致。
DEMO_VIDEO_DIR = Path(__file__).resolve().parent.parent / "uploads" / "courses" / "demo"
DEMO_VIDEO_SECONDS = 10


LEGACY_PAID_TITLES = {"课程导览与学习目标", "核心知识点讲解", "日常执行清单与自测"}


def _add_lesson_rows(db: Session, course: Course, rows) -> None:
    """按 (title, duration, summary, is_trial) 元组批量写入课时。"""
    for index, (title, duration, summary, trial) in enumerate(rows, start=1):
        db.add(
            Lesson(
                course_id=course.id,
                title=title,
                summary=summary,
                video_url="",
                duration_seconds=duration,
                sort_order=index,
                is_trial=trial,
            )
        )


def _replace_lessons(db: Session, course: Course) -> None:
    """删除课程现有课时（含学习进度），用于用真实内容替换旧占位课时。"""
    db.query(LessonProgress).filter(LessonProgress.course_id == course.id).delete(
        synchronize_session=False
    )
    db.query(Lesson).filter(Lesson.course_id == course.id).delete(
        synchronize_session=False
    )


def _ensure_lessons(db: Session, course: Course) -> None:
    """给没有课时的课程补一套课时；每个付费课程第 1 节可试看。

    依据《商业医疗APP技术说明》：免费入门课 2–3 节、每个付费板块 6–8 节、
    每节 8–12 分钟并配 3–5 条要点（见 course_content.py）。
    若课程已有课时但仍是旧版三节占位课，则用真实内容替换。
    """
    from . import course_content

    rows = course_content.lessons_for(course.name)

    existing = (
        db.query(Lesson)
        .filter(Lesson.course_id == course.id)
        .order_by(Lesson.sort_order, Lesson.id)
        .all()
    )
    if existing:
        # 仍是旧版占位课时且已有真实内容 → 替换
        if rows:
            if course.course_type == "intro":
                is_legacy = all(
                    any(l.title.endswith(sfx) for sfx in course_content.LEGACY_INTRO_SUFFIXES)
                    for l in existing
                )
            else:
                is_legacy = {l.title for l in existing} == course_content.LEGACY_PAID_TITLES
            if is_legacy:
                _replace_lessons(db, course)
                _add_lesson_rows(db, course, rows)
                db.commit()
        return

    if rows:
        _add_lesson_rows(db, course, rows)
        return

    # 未配置内容的课程：退回通用三节占位
    generic = [
        ("课程导览与学习目标", 480, "· 本课学习目标与内容导览", True),
        ("核心知识点讲解", 720, "· 核心知识点讲解", False),
        ("日常执行清单与自测", 540, "· 日常执行清单与自测", False),
    ]
    for index, (title, duration, summary, trial) in enumerate(generic, start=1):
        db.add(
            Lesson(
                course_id=course.id,
                title=title,
                summary=summary,
                video_url="",
                duration_seconds=duration,
                sort_order=index,
                is_trial=trial,
            )
        )


def ensure_mall_catalog(db: Session) -> None:
    """补齐商城目录：课程类型/路径/卖点、免费入门课、整包与课时。

    只补空值，不覆盖管理员后续改过的价格与上下架状态。
    """
    courses = db.query(Course).order_by(Course.id).all()
    for course in courses:
        if course.course_type not in ("intro", "single", "bundle"):
            course.course_type = "single"
        if not course.status:
            course.status = "on"
        if not course.valid_days or course.valid_days < 0:
            course.valid_days = 730
        if course.trial_lesson_count is None or course.trial_lesson_count < 0:
            course.trial_lesson_count = 1
        if not course.path_label and course.course_type == "single":
            course.path_label = COPD_PATH_LABELS.get(course.name, "")
        if not course.tagline and course.course_type == "single":
            course.tagline = COPD_TAGLINES.get(course.name, "")
    db.commit()

    # 免费入门课
    intro = (
        db.query(Course)
        .filter(Course.course_type == "intro")
        .order_by(Course.id)
        .first()
    )
    if not intro:
        intro = Course(
            name=INTRO_COURSE_NAME,
            semester="COPD 系列",
            teacher_id=None,
            description=(
                "注册即可免费学习：COPD 是什么、这门课能帮你做什么、"
                "出现哪些情况必须及时就医。"
            ),
            price=0.0,
            cover_url="",
            course_type="intro",
            path_label="免费入门",
            tagline="先了解 COPD 与就医时机，再决定学哪条路径",
            status="on",
            sort_order=0,
            valid_days=0,
            trial_lesson_count=99,
        )
        db.add(intro)
        db.flush()
    else:
        if float(intro.price or 0) != 0:
            intro.price = 0.0
        intro.course_type = "intro"
        intro.path_label = intro.path_label or "免费入门"
        intro.valid_days = 0
        intro.trial_lesson_count = 99
        intro.sort_order = 0

    singles = (
        db.query(Course)
        .filter(Course.course_type == "single")
        .order_by(Course.sort_order, Course.id)
        .all()
    )
    for course in singles:
        if not course.sort_order:
            course.sort_order = 100 + course.id

    # 整包
    bundle = (
        db.query(Course)
        .filter(Course.course_type == "bundle")
        .order_by(Course.id)
        .first()
    )
    if not bundle and singles:
        original = round(sum(float(c.price or 0) for c in singles), 2)
        bundle = Course(
            name=BUNDLE_COURSE_NAME,
            semester="COPD 系列",
            teacher_id=None,
            description=(
                "预防、预测、患病后管理与日常应做事项四个板块一次学完，"
                "含有效期内小版本更新。"
            ),
            price=round(original * 0.7, 2),
            original_price=original,
            cover_url="",
            course_type="bundle",
            path_label="整包",
            tagline="四个板块一次学完，低于单课合计",
            status="on",
            sort_order=10,
            valid_days=730,
            trial_lesson_count=1,
        )
        db.add(bundle)
        db.flush()
    if bundle:
        bundle.sort_order = bundle.sort_order or 10
        has_items = (
            db.query(CourseBundleItem.id)
            .filter(CourseBundleItem.bundle_id == bundle.id)
            .first()
        )
        if not has_items:
            for index, course in enumerate(singles):
                db.add(
                    CourseBundleItem(
                        bundle_id=bundle.id,
                        course_id=course.id,
                        sort_order=index,
                    )
                )

    # 课时
    for course in db.query(Course).order_by(Course.id).all():
        if course.course_type != "bundle":
            _ensure_lessons(db, course)

    # 服务商品字段
    for service in db.query(ServiceProduct).order_by(ServiceProduct.id).all():
        if not service.status:
            service.status = "on"
        if not service.tagline:
            service.tagline = SERVICE_TAGLINES.get(service.name, "")
        if not service.valid_days or service.valid_days < 0:
            service.valid_days = 365
        if not service.sort_order:
            service.sort_order = 100 + service.id
    db.commit()

    attach_demo_lesson_videos(db)


def attach_demo_lesson_videos(db: Session) -> None:
    """本地演示视频存在时，自动挂到还没有视频地址的课时上。

    只补空值，不覆盖管理员填写的真实视频；文件缺失时保持原样。
    """
    if not DEMO_VIDEO_DIR.is_dir():
        return
    changed = False
    for lesson in db.query(Lesson).all():
        if (lesson.video_url or "").strip():
            continue
        candidate = DEMO_VIDEO_DIR / f"lesson-{lesson.id}.mp4"
        if not candidate.is_file():
            continue
        lesson.video_url = f"/uploads/courses/demo/{candidate.name}"
        # 演示片只有几秒，让页面显示的时长与实际一致
        lesson.duration_seconds = DEMO_VIDEO_SECONDS
        changed = True
    if changed:
        db.commit()


def ensure_demo_hospital(db: Session) -> None:
    """演示合作医院；真实医院由管理员在后台开通，地址只放环境变量。"""
    exists = (
        db.query(HospitalPartner)
        .filter(HospitalPartner.code == "demo-hospital")
        .first()
    )
    if exists:
        return
    db.add(
        HospitalPartner(
            code="demo-hospital",
            name="示范合作医院（演示）",
            department="呼吸内科",
            status="enabled",
            mode="demo",
            note="内置演示数据，仅用于功能联调，不作为诊疗依据",
        )
    )
    db.commit()


def seed_if_empty(db: Session) -> None:
    ensure_demo_hospital(db)
    if db.query(User).first():
        ensure_copd_courses(db)
        ensure_demo_avatars(db)
        ensure_demo_urgent_notice(db)
        ensure_demo_materials_grades(db)
        ensure_demo_service_products(db)
        ensure_extra_admin(db)
        ensure_mall_catalog(db)
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
    ensure_mall_catalog(db)
