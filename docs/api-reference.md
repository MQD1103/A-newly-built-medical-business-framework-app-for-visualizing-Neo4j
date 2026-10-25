# 小医后端接口参考

> 本文件由 `backend/scripts/export_api_doc.py` 根据 FastAPI OpenAPI
> 自动生成，请勿手工编辑。接口变更后重新执行脚本即可同步。
> 交互式文档（可试调用）以启动后的 `/docs` 为准。

- 生成时间：2026-10-25 22:11
- 接口总数：140
- OpenAPI 版本：3.1.0

## 认证方式

除标注为「公开」的接口外，均需在请求头携带登录返回的 JWT：

```http
Authorization: Bearer <access_token>
```

令牌通过 `POST /api/auth/login` 获取，有效期由
`ACCESS_TOKEN_EXPIRE_MINUTES` 控制。

## 模块索引

- [管理中心（9）](#admin)
- [AI 用药检测（4）](#ai)
- [登录与账号（6）](#auth)
- [社区（9）](#community)
- [课程与课时（18）](#courses)
- [好友与消息（10）](#friends)
- [成绩（4）](#grades)
- [首页（1）](#home)
- [医院对接（14）](#hospital)
- [关联信息（6）](#links)
- [商城（18）](#mall)
- [资料（3）](#materials)
- [通知公告（4）](#notices)
- [站内通知（9）](#notifications)
- [提醒（6）](#reminders)
- [课表与校历（7）](#schedule)
- [服务商品（6）](#service-products)
- [symptoms（3）](#symptoms)
- [用户（2）](#users)
- [其他（1）](#其他)

## 管理中心

<a id="admin"></a>

- `PATCH /api/admin/reminders/{reminder_id}` — Update Any Reminder
  - 说明：管理员可直接改任意提醒（不经过 reminders.py 的 can_edit 规则）。
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 请求体：`application/json` AdminReminderUpdate（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/admin/reminders/{reminder_id}` — Delete Any Reminder
  - 说明：管理员可删除任意提醒（含系统/管理者来源，普通用户端点做不到）。
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/admin/users/{user_id}` — Update Target User
  - 说明：改他人姓名 / 重置密码（管理员操作，不需要对方旧密码）。
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 请求体：`application/json` AdminUserUpdate（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/admin/users/{user_id}/courses` — Grant Course
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 请求体：`application/json` AdminCourseGrant（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/admin/users/{user_id}/courses/{course_id}` — Revoke Course
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）；`path.course_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/admin/users/{user_id}/overview` — User Overview
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 响应：`200` AdminOverviewOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/admin/users/{user_id}/reminders` — Create Target Reminder
  - 说明：管理员给指定用户下发一条监督提醒（source=manager，用户只可开关提醒）。
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 请求体：`application/json` AdminReminderCreate（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/admin/users/{user_id}/services` — Grant Service
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 请求体：`application/json` AdminServiceGrant（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/admin/users/{user_id}/services/{service_id}` — Revoke Service
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）；`path.service_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## AI 用药检测

<a id="ai"></a>

- `GET /api/ai/medication-checks` — List Medication Checks
  - 认证：需要登录
  - 参数：`query.page`（integer，可选）；`query.page_size`（integer，可选）
  - 响应：`200` MedicationCheckListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/ai/medication-checks` — Analyze Medication
  - 认证：需要登录
  - 请求体：`multipart/form-data` Body_analyze_medication_api_ai_medication_checks_post（必填）
  - 响应：`200` MedicationCheckOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/ai/medication-checks/{check_id}` — Get Medication Check
  - 认证：需要登录
  - 参数：`path.check_id`（integer，必填）
  - 响应：`200` MedicationCheckOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/ai/medication-checks/{check_id}` — Delete Medication Check
  - 认证：需要登录
  - 参数：`path.check_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 登录与账号

<a id="auth"></a>

- `POST /api/auth/avatar` — Upload Avatar
  - 认证：需要登录
  - 请求体：`multipart/form-data` Body_upload_avatar_api_auth_avatar_post（必填）
  - 响应：`200` UserOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/auth/avatar-preview` — Avatar Preview
  - 说明：登录页预览：未设置头像返回 null，前端继续显示蓝球。
  - 认证：公开
  - 参数：`query.username`（string，必填）
  - 响应：`200` AvatarPreviewOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/auth/impersonate` — Impersonate
  - 说明：管理员换用目标用户的身份令牌，用于「以此用户身份进入」。 现有 get_current_user 只读 JWT 的 sub，所以这个令牌在所有端点下与目标用户 自己登录完全等价（creator_id / user_id 都记成目标用户）；act 只是审计预留。
  - 认证：需要登录
  - 请求体：`application/json` ImpersonateIn（必填）
  - 响应：`200` ImpersonateOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/auth/login` — Login
  - 认证：公开
  - 请求体：`application/json` LoginRequest（必填）
  - 响应：`200` Token（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/auth/me` — Me
  - 认证：需要登录
  - 响应：`200` UserOut（Successful Response）
- `PATCH /api/auth/me` — Update Profile
  - 说明：修改姓名；若改密码需提供旧密码。
  - 认证：需要登录
  - 请求体：`application/json` ProfileUpdate（必填）
  - 响应：`200` UserOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 社区

<a id="community"></a>

- `DELETE /api/community/comments/{comment_id}` — Delete Comment
  - 认证：需要登录
  - 参数：`path.comment_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/community/posts` — List Posts
  - 认证：需要登录
  - 参数：`query.scope`（string / all、friends，可选）
  - 响应：`200` array<CommunityPostOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/community/posts` — Create Post
  - 认证：需要登录
  - 请求体：`application/json` CommunityPostCreate（必填）
  - 响应：`200` CommunityPostOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/community/posts/{post_id}` — Delete Post
  - 认证：需要登录
  - 参数：`path.post_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/community/posts/{post_id}/comments` — List Comments
  - 认证：需要登录
  - 参数：`path.post_id`（integer，必填）
  - 响应：`200` array<CommunityCommentOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/community/posts/{post_id}/comments` — Create Comment
  - 认证：需要登录
  - 参数：`path.post_id`（integer，必填）
  - 请求体：`application/json` CommunityCommentCreate（必填）
  - 响应：`200` CommunityCommentOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/community/posts/{post_id}/like` — Toggle Like
  - 认证：需要登录
  - 参数：`path.post_id`（integer，必填）
  - 响应：`200` CommunityPostOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/community/posts/{post_id}/repost` — Repost
  - 认证：需要登录
  - 参数：`path.post_id`（integer，必填）
  - 请求体：`application/json` CommunityRepostCreate（必填）
  - 响应：`200` CommunityPostOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/community/upload` — Upload Community Image
  - 认证：需要登录
  - 请求体：`multipart/form-data` Body_upload_community_image_api_community_upload_post（必填）
  - 响应：`200` CommunityImageOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 课程与课时

<a id="courses"></a>

- `GET /api/courses` — List Courses
  - 说明：售课目录：非管理员只看在售课程；enrolled 表示当前是否有学习权。
  - 认证：需要登录
  - 响应：`200` array<CourseOut>（Successful Response）
- `POST /api/courses` — Create Course
  - 认证：需要登录
  - 请求体：`application/json` CourseCreate（必填）
  - 响应：`200` CourseOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/all` — List All Courses
  - 认证：需要登录
  - 响应：`200` array<CourseOut>（Successful Response）
- `POST /api/courses/enrollments` — Enroll
  - 认证：需要登录
  - 请求体：`application/json` EnrollmentCreate（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/courses/lessons/{lesson_id}` — Update Lesson
  - 认证：需要登录
  - 参数：`path.lesson_id`（integer，必填）
  - 请求体：`application/json` LessonUpdate（必填）
  - 响应：`200` LessonOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/courses/lessons/{lesson_id}` — Delete Lesson
  - 认证：需要登录
  - 参数：`path.lesson_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/courses/lessons/{lesson_id}/progress` — Update Lesson Progress
  - 说明：上报续播位置/完播状态；退款规则按这里的付费课时完成数计算。
  - 认证：需要登录
  - 参数：`path.lesson_id`（integer，必填）
  - 请求体：`application/json` LessonProgressIn（必填）
  - 响应：`200` LessonProgressOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/purchases/mine` — My Purchases
  - 认证：需要登录
  - 响应：`200` array<CoursePurchaseOut>（Successful Response）
- `GET /api/courses/{course_id}` — Get Course
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` CourseOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/courses/{course_id}` — Update Course
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 请求体：`application/json` CourseUpdate（必填）
  - 响应：`200` CourseOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/{course_id}/bundle-items` — List Bundle Items
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` array<CourseOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PUT /api/courses/{course_id}/bundle-items` — Set Bundle Items
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 请求体：`application/json` BundleItemsIn（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/{course_id}/lessons` — List Lessons
  - 说明：课时列表：未购用户也能看到目录；只有试看节/已购课程返回视频地址。
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` CourseLessonsOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/courses/{course_id}/lessons` — Create Lesson
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 请求体：`application/json` LessonCreate（必填）
  - 响应：`200` LessonOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/{course_id}/progress` — Get Course Progress
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` CourseProgressOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/courses/{course_id}/purchase` — Purchase Course
  - 说明：兼容旧前端的「确认即支付」：内部走完整订单 → 模拟支付。
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` CoursePurchaseOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/courses/{course_id}/quiz` — Get Quiz
  - 说明：获取某门课的测验题（不返回答案）。
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 响应：`200` array<QuizQuestionOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/courses/{course_id}/quiz` — Submit Quiz
  - 说明：提交答案：后端判分、返回对错与解析，并保存一次作答记录。
  - 认证：需要登录
  - 参数：`path.course_id`（integer，必填）
  - 请求体：`application/json` QuizSubmitIn（必填）
  - 响应：`200` QuizResultOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 好友与消息

<a id="friends"></a>

- `GET /api/friends` — List Friends
  - 认证：需要登录
  - 响应：`200` array<FriendOut>（Successful Response）
- `GET /api/friends/requests` — List Incoming Requests
  - 认证：需要登录
  - 响应：`200` array<FriendRequestOut>（Successful Response）
- `POST /api/friends/requests` — Request Friend
  - 认证：需要登录
  - 请求体：`application/json` FriendRequestCreate（必填）
  - 响应：`200` FriendRequestResultOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/friends/requests/sent` — List Sent Requests
  - 认证：需要登录
  - 响应：`200` array<FriendRequestOut>（Successful Response）
- `POST /api/friends/requests/{request_id}/accept` — Accept Request
  - 认证：需要登录
  - 参数：`path.request_id`（integer，必填）
  - 响应：`200` FriendRequestResultOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/friends/search` — Search Users
  - 认证：需要登录
  - 参数：`query.q`（string，可选）
  - 响应：`200` array<FriendUserOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/friends/summary` — Summary
  - 认证：需要登录
  - 响应：`200` FriendSummaryOut（Successful Response）
- `DELETE /api/friends/{user_id}` — Remove Friend
  - 说明：统一删除入口：删好友 / 拒绝申请 / 撤销申请都走这里。 只删关系行，聊天记录保留（重新加回仍能看到历史）。
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/friends/{user_id}/messages` — List Messages
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 响应：`200` array<FriendMessageOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/friends/{user_id}/messages` — Send Message
  - 认证：需要登录
  - 参数：`path.user_id`（integer，必填）
  - 请求体：`application/json` FriendMessageCreate（必填）
  - 响应：`200` FriendMessageOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 成绩

<a id="grades"></a>

- `GET /api/grades` — List Grades
  - 认证：需要登录
  - 参数：`query.course_id`（integer | null，可选）
  - 响应：`200` array<GradeOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/grades` — Create Grade
  - 认证：需要登录
  - 请求体：`application/json` GradeCreate（必填）
  - 响应：`200` GradeOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/grades/students` — List Course Students
  - 说明：教师/管理员录入成绩时选择学生。
  - 认证：需要登录
  - 参数：`query.course_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/grades/{grade_id}` — Delete Grade
  - 认证：需要登录
  - 参数：`path.grade_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 首页

<a id="home"></a>

- `GET /api/home` — Home Dashboard
  - 认证：需要登录
  - 响应：`200` HomeOut（Successful Response）

## 医院对接

<a id="hospital"></a>

- `GET /api/hospital/admin/partners` — Admin List Partners
  - 认证：需要登录
  - 响应：`200` array<HospitalPartnerOut>（Successful Response）
- `POST /api/hospital/admin/partners` — Admin Create Partner
  - 认证：需要登录
  - 请求体：`application/json` HospitalPartnerCreate（必填）
  - 响应：`200` HospitalPartnerOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/hospital/admin/partners/{partner_id}` — Admin Update Partner
  - 认证：需要登录
  - 参数：`path.partner_id`（integer，必填）
  - 请求体：`application/json` HospitalPartnerUpdate（必填）
  - 响应：`200` HospitalPartnerOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/hospital/authorizations` — List Authorizations
  - 认证：需要登录
  - 参数：`query.patient_id`（integer | null，可选）
  - 响应：`200` array<HospitalAuthorizationOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/hospital/authorizations` — Create Authorization
  - 认证：需要登录
  - 请求体：`application/json` HospitalAuthorizationCreate（必填）
  - 响应：`200` HospitalAuthorizationOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/hospital/authorizations/{auth_id}` — Revoke Authorization
  - 认证：需要登录
  - 参数：`path.auth_id`（integer，必填）
  - 响应：`200` HospitalAuthorizationOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/hospital/authorizations/{auth_id}/sync` — Sync Authorization
  - 认证：需要登录
  - 参数：`path.auth_id`（integer，必填）
  - 响应：`200` HospitalSyncOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/hospital/caregivers` — List Caregivers
  - 认证：需要登录
  - 响应：`200` HospitalCaregiversOut（Successful Response）
- `POST /api/hospital/caregivers` — Grant Caregiver
  - 认证：需要登录
  - 请求体：`application/json` HospitalCaregiverCreate（必填）
  - 响应：`200` HospitalCaregiverOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/hospital/caregivers/{grant_id}` — Revoke Caregiver
  - 认证：需要登录
  - 参数：`path.grant_id`（integer，必填）
  - 响应：`200` HospitalCaregiverOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/hospital/partners` — List Partners
  - 认证：需要登录
  - 响应：`200` array<HospitalPartnerOut>（Successful Response）
- `GET /api/hospital/records` — List Records
  - 认证：需要登录
  - 参数：`query.patient_id`（integer | null，可选）；`query.record_type`（string | null，可选）
  - 响应：`200` array<HospitalRecordOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/hospital/records/{record_id}` — Get Record
  - 认证：需要登录
  - 参数：`path.record_id`（integer，必填）
  - 响应：`200` HospitalRecordOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/hospital/records/{record_id}/reminder` — Create Reminder From Record
  - 认证：需要登录
  - 参数：`path.record_id`（integer，必填）
  - 请求体：`application/json` HospitalReminderCreate（必填）
  - 响应：`200` HospitalReminderOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 关联信息

<a id="links"></a>

- `GET /api/links/family` — List Family
  - 认证：需要登录
  - 响应：`200` array<FamilyLinkOut>（Successful Response）
- `POST /api/links/family` — Create Family
  - 认证：需要登录
  - 请求体：`application/json` FamilyLinkCreate（必填）
  - 响应：`200` FamilyLinkOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/links/family/{link_id}` — Delete Family
  - 认证：需要登录
  - 参数：`path.link_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/links/hospitals` — List Hospitals
  - 认证：需要登录
  - 响应：`200` array<HospitalLinkOut>（Successful Response）
- `POST /api/links/hospitals` — Create Hospital
  - 认证：需要登录
  - 请求体：`application/json` HospitalLinkCreate（必填）
  - 响应：`200` HospitalLinkOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/links/hospitals/{link_id}` — Delete Hospital
  - 认证：需要登录
  - 参数：`path.link_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 商城

<a id="mall"></a>

- `GET /api/mall/admin/orders` — Admin List Orders
  - 认证：需要登录
  - 参数：`query.status`（string，可选）；`query.product_type`（string，可选）；`query.buyer_id`（integer | null，可选）；`query.page`（integer，可选）；`query.page_size`（integer，可选）
  - 响应：`200` MallOrderListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/admin/orders/{order_no}/refund` — Admin Refund Order
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）；`query.force`（boolean，可选）
  - 请求体：`application/json` MallRefundIn（必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/entitlements` — My Entitlements
  - 认证：需要登录
  - 响应：`200` MallEntitlementsOut（Successful Response）
- `GET /api/mall/my-courses` — My Courses
  - 认证：需要登录
  - 响应：`200` array<MallMyCourseOut>（Successful Response）
- `GET /api/mall/orders` — List My Orders
  - 认证：需要登录
  - 参数：`query.status`（string，可选）；`query.product_type`（string，可选）；`query.page`（integer，可选）；`query.page_size`（integer，可选）
  - 响应：`200` MallOrderListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/orders` — Create Order
  - 说明：创建待支付订单。学习人可与购买人不同；多人学习即团购/代买。
  - 认证：需要登录
  - 请求体：`application/json` MallOrderCreate（必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/orders/mine` — List My Orders
  - 认证：需要登录
  - 参数：`query.status`（string，可选）；`query.product_type`（string，可选）；`query.page`（integer，可选）；`query.page_size`（integer，可选）
  - 响应：`200` MallOrderListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/orders/{order_no}` — Get Order
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/orders/{order_no}/cancel` — Cancel Order
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/orders/{order_no}/pay` — Pay Order
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）
  - 请求体：`application/json` MallPayIn（必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/orders/{order_no}/refund` — Refund Order
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）
  - 请求体：`application/json` MallRefundIn（必填）
  - 响应：`200` MallOrderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/orders/{order_no}/refund-check` — Refund Check
  - 认证：需要登录
  - 参数：`path.order_no`（string，必填）
  - 响应：`200` MallRefundCheckOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/mall/payments/callback` — Payment Callback
  - 说明：支付渠道回调。 演示环境默认不校验签名；配置 MALL_PAYMENT_CALLBACK_TOKEN 后， 回调方必须带 X-Payment-Token 请求头。生产接入真实支付时， 应在此处校验渠道签名并核对金额。
  - 认证：公开
  - 请求体：`application/json` MallPaymentCallbackIn（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/products` — List Products
  - 说明：商城统一商品列表：课程 + 健康服务。
  - 认证：需要登录
  - 参数：`query.product_type`（string，可选）；`query.category`（string，可选）；`query.q`（string，可选）；`query.include_off`（boolean，可选）
  - 响应：`200` MallProductListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/products/{product_type}/{product_id}` — Product Detail
  - 认证：需要登录
  - 参数：`path.product_type`（string，必填）；`path.product_id`（integer，必填）
  - 响应：`200` MallProductDetailOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/refund-policy` — Refund Policy
  - 认证：公开
  - 响应：`200` -（Successful Response）
- `POST /api/mall/seats/redeem` — Redeem Seat
  - 认证：需要登录
  - 请求体：`application/json` MallRedeemIn（必填）
  - 响应：`200` MallRedeemOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/mall/summary` — Mall Summary
  - 认证：需要登录
  - 响应：`200` MallSummaryOut（Successful Response）

## 资料

<a id="materials"></a>

- `GET /api/materials` — List Materials
  - 认证：需要登录
  - 参数：`query.course_id`（integer | null，可选）
  - 响应：`200` array<MaterialOut>（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/materials` — Create Material
  - 认证：需要登录
  - 请求体：`application/json` MaterialCreate（必填）
  - 响应：`200` MaterialOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/materials/{material_id}` — Delete Material
  - 认证：需要登录
  - 参数：`path.material_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 通知公告

<a id="notices"></a>

- `GET /api/notices` — List Notices
  - 认证：需要登录
  - 响应：`200` array<NoticeOut>（Successful Response）
- `POST /api/notices` — Create Notice
  - 认证：需要登录
  - 请求体：`application/json` NoticeCreate（必填）
  - 响应：`200` NoticeOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/notices/{notice_id}` — Get Notice
  - 认证：需要登录
  - 参数：`path.notice_id`（integer，必填）
  - 响应：`200` NoticeOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/notices/{notice_id}` — Delete Notice
  - 认证：需要登录
  - 参数：`path.notice_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 站内通知

<a id="notifications"></a>

- `GET /api/notifications` — List Notifications
  - 认证：需要登录
  - 参数：`query.unread_only`（boolean，可选）；`query.page`（integer，可选）；`query.page_size`（integer，可选）
  - 响应：`200` NotificationListOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/notifications/push/config` — Push Config
  - 说明：前端订阅所需的公开配置；私钥永远不出服务端。
  - 认证：公开
  - 响应：`200` -（Successful Response）
- `GET /api/notifications/push/status` — Push Status
  - 认证：需要登录
  - 响应：`200` -（Successful Response）
- `POST /api/notifications/push/subscribe` — Push Subscribe
  - 认证：需要登录
  - 请求体：`application/json` PushSubscriptionIn（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/notifications/push/test` — Push Test
  - 认证：需要登录
  - 响应：`200` -（Successful Response）
- `POST /api/notifications/push/unsubscribe` — Push Unsubscribe
  - 认证：需要登录
  - 请求体：`application/json` PushUnsubscribeIn（必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/notifications/read-all` — Read All
  - 认证：需要登录
  - 响应：`200` -（Successful Response）
- `GET /api/notifications/summary` — Notification Summary
  - 认证：需要登录
  - 响应：`200` -（Successful Response）
- `POST /api/notifications/{notification_id}/read` — Read One
  - 认证：需要登录
  - 参数：`path.notification_id`（integer，必填）
  - 响应：`200` NotificationOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 提醒

<a id="reminders"></a>

- `GET /api/reminders` — List Reminders
  - 认证：需要登录
  - 响应：`200` array<ReminderOut>（Successful Response）
- `POST /api/reminders` — Create Reminder
  - 说明：任意事项均可添加；课程可选，无课程强制限制。
  - 认证：需要登录
  - 请求体：`application/json` ReminderCreate（必填）
  - 响应：`200` ReminderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/reminders/{reminder_id}` — Update Reminder
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 请求体：`application/json` ReminderUpdate（必填）
  - 响应：`200` ReminderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/reminders/{reminder_id}` — Delete Reminder
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/reminders/{reminder_id}/complete` — Complete Reminder
  - 说明：标记/取消「我已完成」；完成状态只影响当前用户。
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 请求体：`application/json` ReminderDoneUpdate（必填）
  - 响应：`200` ReminderOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PUT /api/reminders/{reminder_id}/notify` — Set Reminder Notify
  - 说明：管理者/系统提醒：用户可开关「是否提醒」，但不能删除。
  - 认证：需要登录
  - 参数：`path.reminder_id`（integer，必填）
  - 请求体：`application/json` ReminderNotifyUpdate（必填）
  - 响应：`200` ReminderOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 课表与校历

<a id="schedule"></a>

- `GET /api/schedule/events` — List Events
  - 认证：需要登录
  - 响应：`200` array<CalendarEventOut>（Successful Response）
- `POST /api/schedule/events` — Create Event
  - 认证：需要登录
  - 请求体：`application/json` CalendarEventCreate（必填）
  - 响应：`200` CalendarEventOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/schedule/events/{event_id}` — Delete Event
  - 认证：需要登录
  - 参数：`path.event_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/schedule/slots` — List Slots
  - 认证：需要登录
  - 响应：`200` array<ScheduleSlotOut>（Successful Response）
- `POST /api/schedule/slots` — Create Slot
  - 认证：需要登录
  - 请求体：`application/json` ScheduleSlotCreate（必填）
  - 响应：`200` ScheduleSlotOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/schedule/slots/{slot_id}` — Delete Slot
  - 认证：需要登录
  - 参数：`path.slot_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/schedule/today` — Today Slots
  - 认证：需要登录
  - 响应：`200` array<ScheduleSlotOut>（Successful Response）

## 服务商品

<a id="service-products"></a>

- `GET /api/service-products` — List Products
  - 认证：需要登录
  - 响应：`200` array<ServiceProductOut>（Successful Response）
- `POST /api/service-products` — Create Product
  - 认证：需要登录
  - 请求体：`application/json` ServiceProductCreate（必填）
  - 响应：`200` ServiceProductOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `GET /api/service-products/purchases/mine` — My Purchases
  - 认证：需要登录
  - 响应：`200` array<ServicePurchaseOut>（Successful Response）
- `GET /api/service-products/{service_id}` — Get Product
  - 认证：需要登录
  - 参数：`path.service_id`（integer，必填）
  - 响应：`200` ServiceProductOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `PATCH /api/service-products/{service_id}` — Update Product
  - 认证：需要登录
  - 参数：`path.service_id`（integer，必填）
  - 请求体：`application/json` ServiceProductUpdate（必填）
  - 响应：`200` ServiceProductOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/service-products/{service_id}/purchase` — Purchase Service
  - 说明：兼容旧前端的「确认即支付」：内部走完整订单 → 模拟支付。
  - 认证：需要登录
  - 参数：`path.service_id`（integer，必填）
  - 响应：`200` ServicePurchaseOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## symptoms

<a id="symptoms"></a>

- `GET /api/symptoms` — Get Diary
  - 认证：需要登录
  - 参数：`query.days`（integer，可选）
  - 响应：`200` SymptomDiaryOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `POST /api/symptoms` — Upsert Entry
  - 说明：同一天再次提交视为更新，不产生重复记录。
  - 认证：需要登录
  - 请求体：`application/json` SymptomEntryIn（必填）
  - 响应：`200` SymptomEntryOut（Successful Response）；`422` HTTPValidationError（Validation Error）
- `DELETE /api/symptoms/{entry_id}` — Delete Entry
  - 认证：需要登录
  - 参数：`path.entry_id`（integer，必填）
  - 响应：`200` -（Successful Response）；`422` HTTPValidationError（Validation Error）

## 用户

<a id="users"></a>

- `GET /api/users` — List Users
  - 认证：需要登录
  - 响应：`200` array<UserOut>（Successful Response）
- `POST /api/users` — Create User
  - 认证：需要登录
  - 请求体：`application/json` UserCreate（必填）
  - 响应：`200` UserOut（Successful Response）；`422` HTTPValidationError（Validation Error）

## 其他

<a id="其他"></a>

- `GET /api/health` — Health
  - 说明：健康检查：同时确认数据库可用，方便排障时区分前后端问题。
  - 认证：公开
  - 响应：`200` -（Successful Response）

## 数据结构

### AdminCourseGrant

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |

### AdminOverviewOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user` | UserOut | 是 |  |
| `courses` | array<CourseOut> | 否 | Courses |
| `services` | array<ServiceProductOut> | 否 | Services |
| `reminders` | array<ReminderOut> | 否 | Reminders |

### AdminReminderCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | Title |
| `content` | string | 否 | Content |
| `due_at` | string (date-time) | 是 | Due At |
| `external_url` | string | 否 | External Url |

### AdminReminderUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | null | 否 | Title |
| `content` | string | null | 否 | Content |
| `due_at` | string | null | 否 | Due At |
| `external_url` | string | null | 否 | External Url |

### AdminServiceGrant

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service_id` | integer | 是 | Service Id |

### AdminUserUpdate

管理员改他人资料：不需要旧密码。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `full_name` | string | null | 否 | Full Name |
| `new_password` | string | null | 否 | New Password |

### AvatarPreviewOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | Username |
| `avatar_url` | string | null | 否 | Avatar Url |

### Body_analyze_medication_api_ai_medication_checks_post

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | string (binary) | 是 | File |
| `lesson_id` | integer | null | 否 | Lesson Id |
| `mode` | string | 否 | Mode；默认 `oral` |

### Body_upload_avatar_api_auth_avatar_post

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | string (binary) | 是 | File |

### Body_upload_community_image_api_community_upload_post

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | string (binary) | 是 | File |

### BundleItemsIn

设置整包包含哪些单课（按给定顺序）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_ids` | array<integer> | 否 | Course Ids |

### CalendarEventCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | Title |
| `event_date` | string (date) | 是 | Event Date |
| `description` | string | 否 | Description |

### CalendarEventOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `title` | string | 是 | Title |
| `event_date` | string (date) | 是 | Event Date |
| `description` | string | 是 | Description |

### CommunityCommentCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 是 | Content |

### CommunityCommentOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `post_id` | integer | 是 | Post Id |
| `author_id` | integer | 是 | Author Id |
| `author_name` | string | 否 | Author Name |
| `author_avatar_url` | string | 否 | Author Avatar Url |
| `content` | string | 是 | Content |
| `created_at` | string (date-time) | 是 | Created At |
| `can_delete` | boolean | 否 | Can Delete；默认 `False` |

### CommunityImageOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | Url |

### CommunityPostCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 否 | Content |
| `image_urls` | array<string> | 否 | Image Urls |

### CommunityPostOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `author_id` | integer | 是 | Author Id |
| `author_name` | string | 否 | Author Name |
| `author_role` | string | 否 | Author Role |
| `author_avatar_url` | string | 否 | Author Avatar Url |
| `author_friend_state` | string | 否 | Author Friend State；默认 `none` |
| `content` | string | 是 | Content |
| `image_urls` | array<string> | 否 | Image Urls |
| `created_at` | string (date-time) | 是 | Created At |
| `can_delete` | boolean | 否 | Can Delete；默认 `False` |
| `like_count` | integer | 否 | Like Count；默认 `0` |
| `liked_by_me` | boolean | 否 | Liked By Me；默认 `False` |
| `comment_count` | integer | 否 | Comment Count；默认 `0` |
| `share_count` | integer | 否 | Share Count；默认 `0` |
| `original_post_id` | integer | null | 否 | Original Post Id |
| `original` | CommunityOriginalOut | null | 否 |  |

### CommunityRepostCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 否 | Content |

### CourseCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Name |
| `semester` | string | 否 | Semester；默认 `COPD 系列` |
| `teacher_id` | integer | null | 否 | Teacher Id |
| `description` | string | 否 | Description |
| `price` | number | 否 | Price；默认 `2.99` |
| `cover_url` | string | 否 | Cover Url |
| `course_type` | string | 否 | Course Type；默认 `single` |
| `path_label` | string | 否 | Path Label |
| `tagline` | string | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | 否 | Status；默认 `on` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `valid_days` | integer | 否 | Valid Days；默认 `730` |
| `trial_lesson_count` | integer | 否 | Trial Lesson Count；默认 `1` |

### CourseLessonsOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 是 | Course Name |
| `owned` | boolean | 否 | Owned；默认 `False` |
| `is_free` | boolean | 否 | Is Free；默认 `False` |
| `trial_lesson_count` | integer | 否 | Trial Lesson Count；默认 `1` |
| `total_lessons` | integer | 否 | Total Lessons；默认 `0` |
| `completed_lessons` | integer | 否 | Completed Lessons；默认 `0` |
| `progress_percent` | number | 否 | Progress Percent；默认 `0.0` |
| `lessons` | array<LessonOut> | 否 | Lessons |

### CourseOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `name` | string | 是 | Name |
| `semester` | string | 是 | Semester |
| `teacher_id` | integer | null | 是 | Teacher Id |
| `teacher_name` | string | 否 | Teacher Name |
| `description` | string | 是 | Description |
| `price` | number | 否 | Price；默认 `2.99` |
| `cover_url` | string | 否 | Cover Url |
| `enrolled` | boolean | 否 | Enrolled；默认 `False` |
| `course_type` | string | 否 | Course Type；默认 `single` |
| `path_label` | string | 否 | Path Label |
| `tagline` | string | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | 否 | Status；默认 `on` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `valid_days` | integer | 否 | Valid Days；默认 `730` |
| `trial_lesson_count` | integer | 否 | Trial Lesson Count；默认 `1` |
| `lesson_count` | integer | 否 | Lesson Count；默认 `0` |
| `expires_at` | string | null | 否 | Expires At |

### CourseProgressOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `owned` | boolean | 否 | Owned；默认 `False` |
| `total_lessons` | integer | 否 | Total Lessons；默认 `0` |
| `completed_lessons` | integer | 否 | Completed Lessons；默认 `0` |
| `percent` | number | 否 | Percent；默认 `0.0` |
| `paid_total` | integer | 否 | Paid Total；默认 `0` |
| `paid_completed` | integer | 否 | Paid Completed；默认 `0` |
| `paid_percent` | number | 否 | Paid Percent；默认 `0.0` |
| `lessons` | array<LessonProgressOut> | 否 | Lessons |

### CoursePurchaseOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 否 | Course Name |
| `amount` | number | 是 | Amount |
| `channel` | string | 否 | Channel；默认 `mock` |
| `status` | string | 否 | Status；默认 `paid` |
| `created_at` | string (date-time) | 是 | Created At |
| `course` | CourseOut | null | 否 |  |
| `order_no` | string | 否 | Order No |
| `quantity` | integer | 否 | Quantity；默认 `1` |
| `unit_price` | number | 否 | Unit Price；默认 `0.0` |
| `original_amount` | number | 否 | Original Amount；默认 `0.0` |
| `discount_amount` | number | 否 | Discount Amount；默认 `0.0` |
| `order_type` | string | 否 | Order Type；默认 `normal` |
| `transaction_id` | string | 否 | Transaction Id |
| `expires_at` | string | null | 否 | Expires At |
| `paid_at` | string | null | 否 | Paid At |
| `valid_until` | string | null | 否 | Valid Until |
| `refund_amount` | number | 否 | Refund Amount；默认 `0.0` |
| `refunded_at` | string | null | 否 | Refunded At |
| `refund_reason` | string | 否 | Refund Reason |

### CourseUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | null | 否 | Name |
| `semester` | string | null | 否 | Semester |
| `teacher_id` | integer | null | 否 | Teacher Id |
| `description` | string | null | 否 | Description |
| `price` | number | null | 否 | Price |
| `cover_url` | string | null | 否 | Cover Url |
| `course_type` | string | null | 否 | Course Type |
| `path_label` | string | null | 否 | Path Label |
| `tagline` | string | null | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | null | 否 | Status |
| `sort_order` | integer | null | 否 | Sort Order |
| `valid_days` | integer | null | 否 | Valid Days |
| `trial_lesson_count` | integer | null | 否 | Trial Lesson Count |

### EnrollmentCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `student_id` | integer | 是 | Student Id |
| `course_id` | integer | 是 | Course Id |

### FamilyLinkCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Name |
| `relation` | string | 否 | Relation；默认 `家人` |
| `phone` | string | 否 | Phone |
| `note` | string | 否 | Note |

### FamilyLinkOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `name` | string | 是 | Name |
| `relation` | string | 是 | Relation |
| `phone` | string | 否 | Phone |
| `note` | string | 否 | Note |
| `created_at` | string (date-time) | 是 | Created At |

### FriendMessageCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 是 | Content |

### FriendMessageOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `sender_id` | integer | 是 | Sender Id |
| `recipient_id` | integer | 是 | Recipient Id |
| `content` | string | 是 | Content |
| `created_at` | string (date-time) | 是 | Created At |
| `mine` | boolean | 否 | Mine；默认 `False` |

### FriendOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | 是 | User Id |
| `username` | string | 否 | Username |
| `full_name` | string | 否 | Full Name |
| `role` | string | 否 | Role |
| `avatar_url` | string | 否 | Avatar Url |
| `friend_state` | string | 否 | Friend State；默认 `none` |
| `last_message` | string | 否 | Last Message |
| `last_message_at` | string | null | 否 | Last Message At |
| `unread_count` | integer | 否 | Unread Count；默认 `0` |

### FriendRequestCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | 是 | User Id |

### FriendRequestOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | 是 | User Id |
| `username` | string | 否 | Username |
| `full_name` | string | 否 | Full Name |
| `role` | string | 否 | Role |
| `avatar_url` | string | 否 | Avatar Url |
| `friend_state` | string | 否 | Friend State；默认 `none` |
| `request_id` | integer | 是 | Request Id |
| `created_at` | string (date-time) | 是 | Created At |
| `direction` | string | 否 | Direction；默认 `incoming` |

### FriendRequestResultOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | integer | null | 否 | Request Id |
| `user_id` | integer | 是 | User Id |
| `status` | string | 是 | Status |
| `auto_accepted` | boolean | 否 | Auto Accepted；默认 `False` |

### FriendSummaryOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pending_requests` | integer | 否 | Pending Requests；默认 `0` |
| `unread_messages` | integer | 否 | Unread Messages；默认 `0` |
| `total` | integer | 否 | Total；默认 `0` |

### FriendUserOut

好友 / 申请人 / 搜索结果的统一用户视图。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | 是 | User Id |
| `username` | string | 否 | Username |
| `full_name` | string | 否 | Full Name |
| `role` | string | 否 | Role |
| `avatar_url` | string | 否 | Avatar Url |
| `friend_state` | string | 否 | Friend State；默认 `none` |

### GradeCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `student_id` | integer | 是 | Student Id |
| `title` | string | 是 | Title |
| `score` | number | 是 | Score |
| `remark` | string | 否 | Remark |

### GradeOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 否 | Course Name |
| `student_id` | integer | 是 | Student Id |
| `student_name` | string | 否 | Student Name |
| `title` | string | 是 | Title |
| `score` | number | 是 | Score |
| `remark` | string | 否 | Remark |
| `creator_id` | integer | 是 | Creator Id |
| `created_at` | string (date-time) | 是 | Created At |
| `can_delete` | boolean | 否 | Can Delete；默认 `False` |

### HTTPValidationError

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `detail` | array<ValidationError> | 否 | Detail |

### HomeOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `today_slots` | array<ScheduleSlotOut> | 是 | Today Slots |
| `upcoming_reminders` | array<ReminderOut> | 是 | Upcoming Reminders |
| `latest_notices` | array<NoticeOut> | 是 | Latest Notices |
| `upcoming_events` | array<CalendarEventOut> | 是 | Upcoming Events |
| `unread_notifications` | integer | 否 | Unread Notifications；默认 `0` |

### HospitalAuthorizationCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `partner_id` | integer | 是 | Partner Id |
| `patient_ref` | string | 是 | Patient Ref |
| `consent` | boolean | 否 | Consent；默认 `False` |

### HospitalAuthorizationOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `partner_id` | integer | 是 | Partner Id |
| `partner_name` | string | 否 | Partner Name |
| `patient_ref_masked` | string | 否 | Patient Ref Masked |
| `scopes` | array<string> | 否 | Scopes |
| `status` | string | 否 | Status；默认 `active` |
| `authorized_at` | string (date-time) | 是 | Authorized At |
| `expires_at` | string | null | 否 | Expires At |
| `revoked_at` | string | null | 否 | Revoked At |

### HospitalCaregiverCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `caregiver_username` | string | 是 | Caregiver Username |
| `relation` | string | 否 | Relation；默认 `照护者` |

### HospitalCaregiverOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `patient_user_id` | integer | 是 | Patient User Id |
| `patient_name` | string | 否 | Patient Name |
| `caregiver_user_id` | integer | 是 | Caregiver User Id |
| `caregiver_name` | string | 否 | Caregiver Name |
| `relation` | string | 否 | Relation；默认 `照护者` |
| `status` | string | 否 | Status；默认 `active` |
| `granted_at` | string (date-time) | 是 | Granted At |
| `revoked_at` | string | null | 否 | Revoked At |

### HospitalCaregiversOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `granted` | array<HospitalCaregiverOut> | 否 | Granted |
| `received` | array<HospitalCaregiverOut> | 否 | Received |

### HospitalLinkCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `hospital_name` | string | 是 | Hospital Name |
| `department` | string | 否 | Department |
| `doctor_name` | string | 否 | Doctor Name |
| `phone` | string | 否 | Phone |
| `address` | string | 否 | Address |
| `note` | string | 否 | Note |

### HospitalLinkOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `hospital_name` | string | 是 | Hospital Name |
| `department` | string | 否 | Department |
| `doctor_name` | string | 否 | Doctor Name |
| `phone` | string | 否 | Phone |
| `address` | string | 否 | Address |
| `note` | string | 否 | Note |
| `created_at` | string (date-time) | 是 | Created At |

### HospitalPartnerCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | Code |
| `name` | string | 是 | Name |
| `department` | string | 否 | Department |
| `mode` | string | 否 | Mode；默认 `demo` |
| `status` | string | 否 | Status；默认 `enabled` |
| `contact` | string | 否 | Contact |
| `note` | string | 否 | Note |

### HospitalPartnerOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `code` | string | 是 | Code |
| `name` | string | 是 | Name |
| `department` | string | 否 | Department |
| `status` | string | 否 | Status；默认 `enabled` |
| `mode` | string | 否 | Mode；默认 `demo` |
| `contact` | string | 否 | Contact |
| `note` | string | 否 | Note |

### HospitalPartnerUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | null | 否 | Name |
| `department` | string | null | 否 | Department |
| `mode` | string | null | 否 | Mode |
| `status` | string | null | 否 | Status |
| `contact` | string | null | 否 | Contact |
| `note` | string | null | 否 | Note |

### HospitalRecordOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `partner_id` | integer | 是 | Partner Id |
| `partner_name` | string | 否 | Partner Name |
| `record_type` | string | 是 | Record Type |
| `title` | string | 是 | Title |
| `content` | string | 否 | Content |
| `doctor_name` | string | 否 | Doctor Name |
| `department` | string | 否 | Department |
| `occurred_at` | string | null | 否 | Occurred At |
| `fetched_at` | string (date-time) | 是 | Fetched At |

### HospitalReminderCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `due_at` | string (date-time) | 是 | Due At |
| `title` | string | null | 否 | Title |
| `content` | string | null | 否 | Content |

### HospitalReminderOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reminder_id` | integer | 是 | Reminder Id |
| `record_id` | integer | 是 | Record Id |
| `title` | string | 是 | Title |
| `due_at` | string (date-time) | 是 | Due At |

### HospitalSyncOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `added` | integer | 否 | Added；默认 `0` |
| `updated` | integer | 否 | Updated；默认 `0` |
| `total` | integer | 否 | Total；默认 `0` |
| `fetched_at` | string (date-time) | 是 | Fetched At |

### ImpersonateIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | 是 | User Id |

### ImpersonateOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `access_token` | string | 是 | Access Token |
| `token_type` | string | 否 | Token Type；默认 `bearer` |
| `user` | UserOut | 是 |  |

### LessonCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | Title |
| `summary` | string | 否 | Summary |
| `video_url` | string | 否 | Video Url |
| `duration_seconds` | integer | 否 | Duration Seconds；默认 `0` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `is_trial` | boolean | 否 | Is Trial；默认 `False` |

### LessonOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | 是 | Course Id |
| `title` | string | 是 | Title |
| `summary` | string | 否 | Summary |
| `video_url` | string | 否 | Video Url |
| `duration_seconds` | integer | 否 | Duration Seconds；默认 `0` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `is_trial` | boolean | 否 | Is Trial；默认 `False` |
| `locked` | boolean | 否 | Locked；默认 `False` |

### LessonProgressIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `position_seconds` | integer | 否 | Position Seconds；默认 `0` |
| `completed` | boolean | null | 否 | Completed |

### LessonProgressOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lesson_id` | integer | 是 | Lesson Id |
| `course_id` | integer | 是 | Course Id |
| `position_seconds` | integer | 否 | Position Seconds；默认 `0` |
| `completed` | boolean | 否 | Completed；默认 `False` |
| `completed_at` | string | null | 否 | Completed At |
| `updated_at` | string | null | 否 | Updated At |

### LessonUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | null | 否 | Title |
| `summary` | string | null | 否 | Summary |
| `video_url` | string | null | 否 | Video Url |
| `duration_seconds` | integer | null | 否 | Duration Seconds |
| `sort_order` | integer | null | 否 | Sort Order |
| `is_trial` | boolean | null | 否 | Is Trial |

### LoginRequest

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | Username |
| `password` | string | 是 | Password |

### MallEntitlementsOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `courses` | array<MallMyCourseOut> | 否 | Courses |
| `services` | array<ServiceProductOut> | 否 | Services |

### MallMyCourseOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course` | CourseOut | 是 |  |
| `source` | string | 否 | Source；默认 `purchase` |
| `expires_at` | string | null | 否 | Expires At |
| `total_lessons` | integer | 否 | Total Lessons；默认 `0` |
| `completed_lessons` | integer | 否 | Completed Lessons；默认 `0` |
| `progress_percent` | number | 否 | Progress Percent；默认 `0.0` |

### MallOrderCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `product_type` | string | 是 | Product Type |
| `product_id` | integer | 是 | Product Id |
| `quantity` | integer | 否 | Quantity；默认 `1` |
| `channel` | string | 否 | Channel；默认 `mock` |
| `learners` | array<MallLearnerIn> | 否 | Learners |
| `remark` | string | 否 | Remark |

### MallOrderListOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array<MallOrderOut> | 否 | Items |
| `total` | integer | 否 | Total；默认 `0` |
| `page` | integer | 否 | Page；默认 `1` |
| `page_size` | integer | 否 | Page Size；默认 `20` |

### MallOrderOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `order_no` | string | 是 | Order No |
| `product_type` | string | 是 | Product Type |
| `product_id` | integer | 是 | Product Id |
| `product_name` | string | 否 | Product Name |
| `product_cover` | string | 否 | Product Cover |
| `product_category` | string | 否 | Product Category |
| `quantity` | integer | 否 | Quantity；默认 `1` |
| `unit_price` | number | 否 | Unit Price；默认 `0.0` |
| `original_amount` | number | 否 | Original Amount；默认 `0.0` |
| `discount_amount` | number | 否 | Discount Amount；默认 `0.0` |
| `amount` | number | 否 | Amount；默认 `0.0` |
| `status` | string | 否 | Status；默认 `pending` |
| `channel` | string | 否 | Channel；默认 `mock` |
| `order_type` | string | 否 | Order Type；默认 `normal` |
| `transaction_id` | string | 否 | Transaction Id |
| `buyer_id` | integer | 是 | Buyer Id |
| `buyer_name` | string | 否 | Buyer Name |
| `created_at` | string (date-time) | 是 | Created At |
| `expires_at` | string | null | 否 | Expires At |
| `paid_at` | string | null | 否 | Paid At |
| `valid_until` | string | null | 否 | Valid Until |
| `cancelled_at` | string | null | 否 | Cancelled At |
| `refunded_at` | string | null | 否 | Refunded At |
| `refund_amount` | number | 否 | Refund Amount；默认 `0.0` |
| `refund_reason` | string | 否 | Refund Reason |
| `upgrade_from_order_id` | integer | null | 否 | Upgrade From Order Id |
| `upgrade_source_order_nos` | array<string> | 否 | Upgrade Source Order Nos |
| `seats` | array<MallOrderSeatOut> | 否 | Seats |
| `can_pay` | boolean | 否 | Can Pay；默认 `False` |
| `can_cancel` | boolean | 否 | Can Cancel；默认 `False` |
| `refundable` | boolean | 否 | Refundable；默认 `False` |
| `refund_hint` | string | 否 | Refund Hint |

### MallPayIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `channel` | string | 否 | Channel；默认 `mock` |
| `transaction_id` | string | 否 | Transaction Id |

### MallPaymentCallbackIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `order_no` | string | 是 | Order No |
| `transaction_id` | string | 否 | Transaction Id |
| `channel` | string | 否 | Channel；默认 `mock` |
| `status` | string | 否 | Status；默认 `success` |

### MallProductDetailOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `product_type` | string | 是 | Product Type |
| `id` | integer | 是 | Id |
| `name` | string | 是 | Name |
| `subtitle` | string | 否 | Subtitle |
| `description` | string | 否 | Description |
| `price` | number | 否 | Price；默认 `0.0` |
| `original_price` | number | null | 否 | Original Price |
| `cover_url` | string | 否 | Cover Url |
| `category` | string | 否 | Category |
| `unit_label` | string | 否 | Unit Label |
| `badge` | string | 否 | Badge |
| `course_type` | string | 否 | Course Type |
| `path_label` | string | 否 | Path Label |
| `valid_days` | integer | 否 | Valid Days；默认 `0` |
| `lesson_count` | integer | 否 | Lesson Count；默认 `0` |
| `trial_lesson_count` | integer | 否 | Trial Lesson Count；默认 `0` |
| `owned` | boolean | 否 | Owned；默认 `False` |
| `expires_at` | string | null | 否 | Expires At |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `included_courses` | array<MallIncludedCourseOut> | 否 | Included Courses |
| `lessons` | array<LessonOut> | 否 | Lessons |
| `upgrade_quote` | MallUpgradeQuoteOut | null | 否 |  |
| `refund_policy` | string | 否 | Refund Policy |

### MallProductListOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array<MallProductOut> | 否 | Items |
| `total` | integer | 否 | Total；默认 `0` |

### MallRedeemIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `activation_code` | string | 是 | Activation Code |

### MallRedeemOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ok` | boolean | 否 | Ok；默认 `True` |
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 否 | Course Name |
| `learner_name` | string | 否 | Learner Name |
| `expires_at` | string | null | 否 | Expires At |

### MallRefundCheckOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eligible` | boolean | 否 | Eligible；默认 `False` |
| `reason` | string | 否 | Reason |
| `refund_amount` | number | 否 | Refund Amount；默认 `0.0` |
| `within_window` | boolean | 否 | Within Window；默认 `False` |
| `window_ends_at` | string | null | 否 | Window Ends At |
| `progress_percent` | number | 否 | Progress Percent；默认 `0.0` |
| `policy` | string | 否 | Policy |

### MallRefundIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | string | 否 | Reason |

### MallSummaryOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_count` | integer | 否 | Course Count；默认 `0` |
| `service_count` | integer | 否 | Service Count；默认 `0` |
| `owned_course_count` | integer | 否 | Owned Course Count；默认 `0` |
| `owned_service_count` | integer | 否 | Owned Service Count；默认 `0` |
| `pending_orders` | integer | 否 | Pending Orders；默认 `0` |
| `paid_orders` | integer | 否 | Paid Orders；默认 `0` |
| `refund_policy` | string | 否 | Refund Policy |

### MaterialCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `title` | string | 是 | Title |
| `url` | string | 否 | Url |
| `note` | string | 否 | Note |

### MaterialOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 否 | Course Name |
| `title` | string | 是 | Title |
| `url` | string | 否 | Url |
| `note` | string | 否 | Note |
| `creator_id` | integer | 是 | Creator Id |
| `created_at` | string (date-time) | 是 | Created At |
| `can_delete` | boolean | 否 | Can Delete；默认 `False` |

### MedicationCheckListOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array<MedicationCheckOut> | 否 | Items |
| `total` | integer | 否 | Total；默认 `0` |
| `page` | integer | 否 | Page；默认 `1` |
| `page_size` | integer | 否 | Page Size；默认 `20` |
| `retention_days` | integer | 否 | Retention Days；默认 `30` |
| `disclaimer` | string | 否 | Disclaimer |

### MedicationCheckOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `user_id` | integer | 是 | User Id |
| `lesson_id` | integer | null | 否 | Lesson Id |
| `status` | string | 否 | Status；默认 `completed` |
| `provider` | string | 否 | Provider；默认 `demo` |
| `mode` | string | 否 | Mode；默认 `oral` |
| `steps` | array<MedicationStepOut> | 否 | Steps |
| `needs_retry` | boolean | 否 | Needs Retry；默认 `False` |
| `message` | string | 否 | Message |
| `image_size` | integer | 否 | Image Size；默认 `0` |
| `image_type` | string | 否 | Image Type |
| `created_at` | string (date-time) | 是 | Created At |
| `expires_at` | string | null | 否 | Expires At |
| `disclaimer` | string | 否 | Disclaimer |

### NoticeCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | Title |
| `body` | string | 是 | Body |
| `audience` | string | 否 | Audience；默认 `all` |
| `is_urgent` | boolean | 否 | Is Urgent；默认 `False` |

### NoticeOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `title` | string | 是 | Title |
| `body` | string | 是 | Body |
| `audience` | string | 是 | Audience |
| `is_urgent` | boolean | 否 | Is Urgent；默认 `False` |
| `author_id` | integer | 是 | Author Id |
| `author_name` | string | 否 | Author Name |
| `created_at` | string (date-time) | 是 | Created At |

### NotificationListOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array<NotificationOut> | 否 | Items |
| `total` | integer | 否 | Total；默认 `0` |
| `unread` | integer | 否 | Unread；默认 `0` |
| `page` | integer | 否 | Page；默认 `1` |
| `page_size` | integer | 否 | Page Size；默认 `20` |

### NotificationOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `user_id` | integer | 是 | User Id |
| `reminder_id` | integer | 是 | Reminder Id |
| `course_id` | integer | null | 否 | Course Id |
| `course_name` | string | 否 | Course Name |
| `trigger_key` | string | 否 | Trigger Key；默认 `due` |
| `title` | string | 是 | Title |
| `body` | string | 否 | Body |
| `external_url` | string | 否 | External Url |
| `due_at` | string | null | 否 | Due At |
| `created_at` | string (date-time) | 是 | Created At |
| `read_at` | string | null | 否 | Read At |
| `read` | boolean | 否 | Read；默认 `False` |
| `click_url` | string | 否 | Click Url |

### ProfileUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `full_name` | string | null | 否 | Full Name |
| `old_password` | string | null | 否 | Old Password |
| `new_password` | string | null | 否 | New Password |

### PushSubscriptionIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `endpoint` | string | 是 | Endpoint |
| `keys` | PushSubscriptionKeysIn | 是 |  |
| `user_agent` | string | 否 | User Agent |

### PushUnsubscribeIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `endpoint` | string | 是 | Endpoint |

### QuizQuestionOut

下发给前端的题目：不带答案，防作弊。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `question` | string | 是 | Question |
| `options` | array<string> | 否 | Options |

### QuizResultOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `score` | integer | 是 | Score |
| `total` | integer | 是 | Total |
| `details` | array<QuizDetailOut> | 否 | Details |

### QuizSubmitIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `answers` | object | 否 | Answers |

### ReminderCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | Title |
| `content` | string | 否 | Content |
| `due_at` | string (date-time) | 是 | Due At |
| `external_url` | string | 否 | External Url |
| `course_id` | integer | null | 否 | Course Id |
| `kind` | string | 否 | Kind；默认 `general` |
| `drug_name` | string | 否 | Drug Name |
| `dosage` | string | 否 | Dosage |
| `repeat_rule` | string | 否 | Repeat Rule；默认 `none` |
| `check_type` | string | 否 | Check Type |
| `prep_questions` | string | 否 | Prep Questions |

### ReminderDoneUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `completed` | boolean | 否 | Completed；默认 `True` |

### ReminderNotifyUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `enabled` | boolean | 是 | Enabled |

### ReminderOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | null | 否 | Course Id |
| `course_name` | string | 否 | Course Name |
| `title` | string | 是 | Title |
| `content` | string | 是 | Content |
| `due_at` | string (date-time) | 是 | Due At |
| `external_url` | string | 是 | External Url |
| `creator_id` | integer | 是 | Creator Id |
| `target_user_id` | integer | null | 否 | Target User Id |
| `created_at` | string (date-time) | 是 | Created At |
| `status` | string | 否 | Status；默认 `pending` |
| `source` | string | 否 | Source；默认 `manager` |
| `notify_enabled` | boolean | 否 | Notify Enabled；默认 `True` |
| `completed` | boolean | 否 | Completed；默认 `False` |
| `completed_at` | string | null | 否 | Completed At |
| `can_delete` | boolean | 否 | Can Delete；默认 `False` |
| `can_edit` | boolean | 否 | Can Edit；默认 `False` |
| `kind` | string | 否 | Kind；默认 `general` |
| `drug_name` | string | 否 | Drug Name |
| `dosage` | string | 否 | Dosage |
| `repeat_rule` | string | 否 | Repeat Rule；默认 `none` |
| `check_type` | string | 否 | Check Type |
| `prep_questions` | string | 否 | Prep Questions |
| `recurring_parent_id` | integer | null | 否 | Recurring Parent Id |

### ReminderUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | null | 否 | Title |
| `content` | string | null | 否 | Content |
| `due_at` | string | null | 否 | Due At |
| `external_url` | string | null | 否 | External Url |
| `course_id` | integer | null | 否 | Course Id |
| `kind` | string | null | 否 | Kind |
| `drug_name` | string | null | 否 | Drug Name |
| `dosage` | string | null | 否 | Dosage |
| `repeat_rule` | string | null | 否 | Repeat Rule |
| `check_type` | string | null | 否 | Check Type |
| `prep_questions` | string | null | 否 | Prep Questions |

### ScheduleSlotCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | integer | 是 | Course Id |
| `weekday` | integer | 是 | Weekday |
| `start_time` | string | 是 | Start Time |
| `end_time` | string | 是 | End Time |
| `location` | string | 否 | Location |

### ScheduleSlotOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `course_id` | integer | 是 | Course Id |
| `course_name` | string | 否 | Course Name |
| `weekday` | integer | 是 | Weekday |
| `start_time` | string | 是 | Start Time |
| `end_time` | string | 是 | End Time |
| `location` | string | 是 | Location |

### ServiceProductCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Name |
| `category` | string | 否 | Category；默认 `健康服务` |
| `description` | string | 否 | Description |
| `price` | number | 否 | Price；默认 `9.9` |
| `cover_url` | string | 否 | Cover Url |
| `unit_label` | string | 否 | Unit Label；默认 `单次` |
| `tagline` | string | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | 否 | Status；默认 `on` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `valid_days` | integer | 否 | Valid Days；默认 `365` |

### ServiceProductOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `name` | string | 是 | Name |
| `category` | string | 是 | Category |
| `description` | string | 是 | Description |
| `price` | number | 否 | Price；默认 `9.9` |
| `cover_url` | string | 否 | Cover Url |
| `unit_label` | string | 否 | Unit Label；默认 `单次` |
| `owned` | boolean | 否 | Owned；默认 `False` |
| `tagline` | string | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | 否 | Status；默认 `on` |
| `sort_order` | integer | 否 | Sort Order；默认 `0` |
| `valid_days` | integer | 否 | Valid Days；默认 `365` |
| `expires_at` | string | null | 否 | Expires At |

### ServiceProductUpdate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | null | 否 | Name |
| `category` | string | null | 否 | Category |
| `description` | string | null | 否 | Description |
| `price` | number | null | 否 | Price |
| `cover_url` | string | null | 否 | Cover Url |
| `unit_label` | string | null | 否 | Unit Label |
| `tagline` | string | null | 否 | Tagline |
| `original_price` | number | null | 否 | Original Price |
| `status` | string | null | 否 | Status |
| `sort_order` | integer | null | 否 | Sort Order |
| `valid_days` | integer | null | 否 | Valid Days |

### ServicePurchaseOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `service_id` | integer | 是 | Service Id |
| `service_name` | string | 否 | Service Name |
| `amount` | number | 是 | Amount |
| `channel` | string | 否 | Channel；默认 `mock` |
| `status` | string | 否 | Status；默认 `paid` |
| `created_at` | string (date-time) | 是 | Created At |
| `service` | ServiceProductOut | null | 否 |  |
| `order_no` | string | 否 | Order No |
| `quantity` | integer | 否 | Quantity；默认 `1` |
| `unit_price` | number | 否 | Unit Price；默认 `0.0` |
| `original_amount` | number | 否 | Original Amount；默认 `0.0` |
| `discount_amount` | number | 否 | Discount Amount；默认 `0.0` |
| `order_type` | string | 否 | Order Type；默认 `normal` |
| `transaction_id` | string | 否 | Transaction Id |
| `expires_at` | string | null | 否 | Expires At |
| `paid_at` | string | null | 否 | Paid At |
| `valid_until` | string | null | 否 | Valid Until |
| `refund_amount` | number | 否 | Refund Amount；默认 `0.0` |
| `refunded_at` | string | null | 否 | Refunded At |
| `refund_reason` | string | 否 | Refund Reason |

### SymptomDiaryOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array<SymptomEntryOut> | 否 | Items |
| `warning` | boolean | 否 | Warning；默认 `False` |
| `warning_text` | string | 否 | Warning Text |
| `disclaimer` | string | 否 | Disclaimer |

### SymptomEntryIn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `record_date` | string | null | 否 | Record Date |
| `cough` | integer | 否 | Cough；默认 `0` |
| `dyspnea` | integer | 否 | Dyspnea；默认 `0` |
| `sputum` | integer | 否 | Sputum；默认 `0` |
| `note` | string | 否 | Note |

### SymptomEntryOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `record_date` | string (date) | 是 | Record Date |
| `cough` | integer | 否 | Cough；默认 `0` |
| `dyspnea` | integer | 否 | Dyspnea；默认 `0` |
| `sputum` | integer | 否 | Sputum；默认 `0` |
| `note` | string | 否 | Note |
| `total` | integer | 否 | Total；默认 `0` |
| `warning` | boolean | 否 | Warning；默认 `False` |
| `warning_text` | string | 否 | Warning Text |
| `created_at` | string (date-time) | 是 | Created At |
| `updated_at` | string (date-time) | 是 | Updated At |

### Token

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `access_token` | string | 是 | Access Token |
| `token_type` | string | 否 | Token Type；默认 `bearer` |

### UserCreate

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | Username |
| `password` | string | 是 | Password |
| `full_name` | string | 是 | Full Name |
| `role` | string | 是 | Role |

### UserOut

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | integer | 是 | Id |
| `username` | string | 是 | Username |
| `full_name` | string | 是 | Full Name |
| `role` | string | 是 | Role |
| `avatar_url` | string | 否 | Avatar Url |
