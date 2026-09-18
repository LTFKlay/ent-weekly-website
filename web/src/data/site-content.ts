export const siteContent = {
  project: {
    eyebrow: 'About the project',
    title: '项目简介',
    intro: 'ENT Weekly 是面向耳鼻喉科的 PubMed 文献追踪网站，按入库日期整理并提供中文阅读辅助。',
    sections: [
      ['覆盖范围', '鼻科、耳科、咽喉科和鼻咽癌；展示临床研究、基础研究、AI/ML、综述 Meta 与指南共识。'],
      ['更新方式', '每日北京时间 14:00 追踪 PubMed 新入库文献，并按入库日期归档；周报页面汇集后续的主题综述。'],
      ['阅读说明', '中文标题和摘要为辅助阅读内容；研究设计、原始摘要和 PubMed 原文链接始终保留'],
    ],
  },
  changelog: {
    eyebrow: 'Release notes',
    title: '更新日志',
    intro: '记录网站功能和内容呈现的主要调整。',
    entries: [
      ['2026-09-17', '完成文献日期、专科与研究类型的组合筛选；新增详情页、主题分类与 PubMed 原文入口。'],
      ['2026-09-17', '优化文献卡片信息层级，调整 IF、作者与作者单位的展示方式。'],
      ['2026-09-17', '建立 PubMed EDAT 检索、分类翻译、SQLite 与静态快照的基础数据流程。'],
    ],
  },
  feedback: {
    eyebrow: 'Feedback',
    title: '反馈',
    intro: '如发现抓取遗漏、分类错误、翻译不准，或希望添加新功能，请联系作者',
    sections: [
      ['作者', 'KlayLTF'],
      ['联系渠道', 'ltfklay2023@163.com'],
      ['致谢', '本项目感谢@Linastro开源'],
    ],
  },
  author: {
    eyebrow: 'Credits',
    title: '作者',
    intro: 'ENT Weekly 编辑团队',
    sections: [
      ['项目职责', '负责检索规则维护、质量筛选、内容校对与网站运营。'],
      ['作者信息', '请在此处填写作者姓名、所属机构、专业方向及公开联系方式。'],
    ],
  },
} as const;
