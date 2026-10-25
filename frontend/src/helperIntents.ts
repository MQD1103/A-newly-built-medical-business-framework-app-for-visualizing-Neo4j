/**
 * 首页小助手的意图库与匹配逻辑。
 * 纯函数、无 React 依赖，方便单独调试；按关键词权重命中功能路由。
 */
export type Intent = {
  to: string
  label: string
  /** [关键词, 权重]，权重越大越具体 */
  keywords: Array<[string, number]>
  adminOnly?: boolean
}

export const INTENTS: Intent[] = [
  {
    to: '/scores',
    label: '成绩',
    keywords: [
      ['成绩', 9],
      ['成绩单', 9],
      ['分数', 8],
      ['考核', 7],
      ['得分', 7],
      ['测验结果', 8],
      ['考试成绩', 9],
      ['考试结果', 8],
    ],
  },
  {
    to: '/schedule',
    label: '课表 / 校历',
    keywords: [
      ['课表', 9],
      ['课程表', 9],
      ['校历', 9],
      ['日程', 7],
      ['时间表', 7],
      ['上课时间', 7],
      ['教室', 6],
      ['考试', 6],
      ['考试安排', 7],
      ['放假', 7],
      ['假期', 6],
    ],
  },
  {
    to: '/reminders',
    label: '提醒',
    keywords: [
      ['提醒', 9],
      ['待办', 8],
      ['截止', 7],
      ['到期', 7],
      ['倒计时', 7],
      ['别忘', 5],
    ],
  },
  {
    to: '/notifications',
    label: '消息通知',
    keywords: [
      ['消息通知', 16],
      ['手机通知', 16],
      ['消息中心', 15],
      ['通知栏', 14],
      ['推送', 14],
      ['我的消息', 14],
    ],
  },
  {
    to: '/notices',
    label: '通知公告',
    keywords: [
      ['公告', 9],
      ['通知', 8],
      ['校级通知', 9],
      ['紧急公告', 9],
      ['消息', 5],
      ['新闻', 5],
    ],
  },
  {
    to: '/community',
    label: '社区',
    keywords: [
      ['社区', 9],
      ['动态', 7],
      ['发帖', 8],
      ['帖子', 7],
      ['广场', 7],
      ['圈子', 7],
      ['分享', 4],
    ],
  },
  {
    to: '/friends',
    label: '好友与私信',
    keywords: [
      ['好友', 9],
      ['加好友', 10],
      ['私信', 9],
      ['聊天', 8],
      ['朋友', 7],
      ['发消息', 7],
      ['通讯录', 8],
    ],
  },
  {
    to: '/courses',
    label: '课程',
    keywords: [
      ['课程', 9],
      ['买课', 10],
      ['购课', 10],
      ['网课', 9],
      ['小测', 8],
      ['测验', 8],
      ['章节', 7],
      ['课时', 7],
      ['续播', 7],
      ['播放', 6],
      ['学习', 5],
      ['上课', 5],
      ['视频', 5],
    ],
  },
  {
    to: '/materials',
    label: '课程资料',
    keywords: [
      ['课程资料', 10],
      ['课件', 9],
      ['讲义', 9],
      ['教材', 8],
      ['资料', 6],
      ['素材', 6],
      ['下载', 4],
    ],
  },
  {
    to: '/service-shop',
    label: '服务商城',
    keywords: [
      ['服务商城', 10],
      ['健康服务', 9],
      ['买服务', 9],
      ['随访', 8],
      ['康复指导', 8],
      ['用药托管', 8],
      ['护理', 6],
      ['咨询', 5],
    ],
  },
  {
    to: '/supervision',
    label: '健康监督',
    keywords: [
      ['监督', 9],
      ['打卡', 8],
      ['用药打卡', 9],
      ['随访提醒', 8],
      ['健康监测', 8],
    ],
  },
  {
    to: '/symptom-diary',
    label: '症状日记',
    keywords: [
      ['症状日记', 10],
      ['症状记录', 9],
      ['咳嗽记录', 8],
      ['气短记录', 8],
      ['记录症状', 9],
    ],
  },
  {
    to: '/ai-check',
    label: '用药动作检测',
    keywords: [
      ['用药动作检测', 11],
      ['动作检测', 9],
      ['用药检测', 9],
      ['拍药', 8],
      ['吸药检测', 9],
      ['用药拍照', 9],
    ],
  },
  {
    to: '/hospital',
    label: '医院资料',
    keywords: [
      ['医院资料', 10],
      ['医院记录', 9],
      ['医嘱', 9],
      ['医生嘱托', 10],
      ['病历', 7],
      ['授权医院', 9],
    ],
  },
  {
    to: '/orders',
    label: '我的订单',
    keywords: [
      ['我的订单', 10],
      ['订单', 7],
      ['退款', 9],
      ['激活码', 9],
      ['兑换课程', 9],
      ['团购', 8],
      ['我的课程', 9],
    ],
  },
  {
    to: '/mall',
    label: '商城',
    keywords: [
      ['商城', 9],
      ['商店', 8],
      ['商品', 8],
      ['购买', 6],
      ['价格', 5],
      ['多少钱', 5],
      ['付费', 5],
      ['买', 3],
    ],
  },
  {
    to: '/services',
    label: '服务',
    keywords: [
      ['服务', 6],
      ['服务大厅', 9],
      ['常用服务', 9],
    ],
  },
  {
    to: '/linked',
    label: '关联信息',
    keywords: [
      ['关联信息', 10],
      ['关联', 8],
      ['家人', 7],
      ['家属', 7],
      ['医院', 7],
      ['绑定', 7],
    ],
  },
  {
    to: '/profile',
    label: '修改资料',
    keywords: [
      ['修改资料', 10],
      ['改资料', 10],
      ['资料修改', 10],
      ['编辑资料', 10],
      ['个人资料', 9],
      ['我的资料', 9],
      ['改密码', 9],
      ['密码', 7],
    ],
  },
  {
    to: '/me',
    label: '我的',
    keywords: [
      ['换头像', 9],
      ['个人主页', 8],
      ['个人中心', 8],
      ['我的账号', 8],
      ['退出登录', 8],
      ['头像', 7],
      ['主页', 5],
      ['我的', 4],
    ],
  },
  {
    to: '/manage',
    label: '管理中心',
    adminOnly: true,
    keywords: [
      ['管理中心', 10],
      ['后台管理', 10],
      ['用户管理', 9],
      ['加学生', 8],
      ['权限', 7],
      ['管理', 6],
    ],
  },
  {
    to: '/admin-user',
    label: '管理员代办',
    adminOnly: true,
    keywords: [
      ['管理员代办', 11],
      ['替用户', 9],
      ['切换身份', 9],
      ['以用户身份', 9],
      ['开通课程', 8],
      ['代办', 8],
    ],
  },
  {
    to: '/',
    label: '首页',
    keywords: [
      ['首页', 9],
      ['回到首页', 10],
      ['主页', 6],
    ],
  },
]

export const SUGGESTIONS = ['我的成绩', '课表', '买课', '加好友', '提醒', '商城']

/** 去掉空白与标点，避免“成 绩”“成绩？”这类输入匹配不上 */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\s,，。.!！?？、;；:：'"“”‘’()（）\-—_/\\|~·]+/g, '')
}

/** 低于该分数视为没听懂，避免“我”“课”这类单字乱跳 */
const MIN_SCORE = 4

export function matchIntent(text: string, isAdmin: boolean): Intent | null {
  const query = normalize(text)
  if (!query) return null
  let best: { intent: Intent; score: number } | null = null
  for (const intent of INTENTS) {
    if (intent.adminOnly && !isAdmin) continue
    let score = 0
    for (const [word, weight] of intent.keywords) {
      if (query.includes(normalize(word))) score += weight
    }
    if (score > 0 && (!best || score > best.score)) best = { intent, score }
  }
  return best && best.score >= MIN_SCORE ? best.intent : null
}

/** 非管理员输入了管理相关字眼时的解释，而非笼统的“没听懂” */
export function isAdminOnlyRequest(text: string): boolean {
  return /管理|代办|切换身份|开通课程/.test(normalize(text))
}
