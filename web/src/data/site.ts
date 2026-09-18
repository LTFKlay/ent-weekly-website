import fs from 'node:fs';
import path from 'node:path';

export type Article = {
  pmid: string;
  specialty: '鼻科' | '耳科' | '咽喉科' | '鼻咽癌';
  category: '临床研究' | 'AI/ML' | '基础研究' | '综述 Meta' | '指南共识';
  evidenceTrack: '临床' | '基础／转化';
  journal: string;
  publicationDate: string;
  jcr: 'Q1' | 'Q2' | 'Q3';
  fiveYearJif: number;
  titleZh: string;
  titleEn: string;
  authors: string[];
  affiliations: string[];
  abstractZh: string;
  abstractEn: string;
  sourceDates: string;
  entryDate?: string;
};

const demoArticles: Article[] = [
  { pmid: 'DEMO-1001', specialty: '鼻科', category: '临床研究', evidenceTrack: '临床', journal: 'International Forum of Allergy & Rhinology', publicationDate: '2026-09-12', jcr: 'Q1', fiveYearJif: 4.2, titleZh: '慢性鼻窦炎生物制剂治疗的真实世界结局：多中心队列研究', titleEn: 'Real-world outcomes of biologic therapy in chronic rhinosinusitis: a multicentre cohort study.', authors: ['演示作者 A', '演示作者 B'], affiliations: ['演示单位：耳鼻咽喉头颈外科'], abstractZh: '【演示数据】正式上线后，此处完整呈现由 DeepSeek 翻译的 PubMed 摘要；不补充原文未报告的研究结果、效应量或临床意义。', abstractEn: '[DEMO DATA] The production site preserves the complete PubMed abstract verbatim, in its original language and section order.', sourceDates: 'EDAT 2026-09-12；PDAT 2026-09-10', entryDate: '2026-09-12' },
  { pmid: 'DEMO-1002', specialty: '耳科', category: '临床研究', evidenceTrack: '临床', journal: 'Otology & Neurotology', publicationDate: '2026-09-11', jcr: 'Q2', fiveYearJif: 2.7, titleZh: '人工耳蜗植入术后言语识别恢复的纵向评估', titleEn: 'Longitudinal assessment of speech recognition recovery after cochlear implantation.', authors: ['演示作者 C'], affiliations: ['演示单位：听觉医学中心'], abstractZh: '【演示数据】此区域用于验证中文摘要与英文原文并列呈现的阅读体验。', abstractEn: '[DEMO DATA] The complete PubMed abstract will be retained here after the quality gate and translation pipeline succeed.', sourceDates: 'EDAT 2026-09-11' },
  { pmid: 'DEMO-1003', specialty: '咽喉科', category: '基础研究', evidenceTrack: '基础／转化', journal: 'Laryngoscope Investigative Otolaryngology', publicationDate: '2026-09-10', jcr: 'Q2', fiveYearJif: 2.2, titleZh: '喉鳞状细胞癌免疫微环境的单细胞图谱', titleEn: 'Single-cell mapping of the immune microenvironment in laryngeal squamous cell carcinoma.', authors: ['演示作者 D'], affiliations: ['演示单位：肿瘤转化医学中心'], abstractZh: '【演示数据】此处将保留完整摘要译文并标记基础／转化证据边界。', abstractEn: '[DEMO DATA] This placeholder represents a complete original abstract in the production pipeline.', sourceDates: 'EDAT 2026-09-10；PDAT 2026-09-09' },
  { pmid: 'DEMO-1004', specialty: '鼻咽癌', category: 'AI/ML', evidenceTrack: '临床', journal: 'Oral Oncology', publicationDate: '2026-09-10', jcr: 'Q1', fiveYearJif: 4.5, titleZh: '循环 EBV DNA 指导鼻咽癌治疗后风险分层', titleEn: 'Circulating EBV DNA-guided risk stratification after treatment for nasopharyngeal carcinoma.', authors: ['演示作者 E'], affiliations: ['演示单位：鼻咽癌多学科中心'], abstractZh: '【演示数据】真实记录会清晰分离临床研究与 AI/ML 展示类别。', abstractEn: '[DEMO DATA] Production abstracts are stored verbatim from PubMed.', sourceDates: 'EDAT 2026-09-10' },
  { pmid: 'DEMO-1005', specialty: '鼻科', category: '综述 Meta', evidenceTrack: '临床', journal: 'Rhinology', publicationDate: '2026-09-09', jcr: 'Q1', fiveYearJif: 3.6, titleZh: '嗅觉上皮再生中的神经免疫互作', titleEn: 'Neuroimmune interactions in olfactory epithelial regeneration.', authors: ['演示作者 F'], affiliations: ['演示单位：鼻科学研究室'], abstractZh: '【演示数据】正式版会将综述与原始研究区别标记。', abstractEn: '[DEMO DATA] Production abstracts retain their original order.', sourceDates: 'EDAT 2026-09-09' },
  { pmid: 'DEMO-1006', specialty: '咽喉科', category: '指南共识', evidenceTrack: '临床', journal: 'Head & Neck', publicationDate: '2026-09-08', jcr: 'Q1', fiveYearJif: 4.1, titleZh: '经口机器人手术治疗早期口咽癌的功能结局', titleEn: 'Functional outcomes after transoral robotic surgery for early oropharyngeal cancer.', authors: ['演示作者 G'], affiliations: ['演示单位：头颈外科'], abstractZh: '【演示数据】上线后仅纳入通过 JCR/CAS 门禁的真实 PubMed 记录。', abstractEn: '[DEMO DATA] This placeholder exists solely for layout validation.', sourceDates: 'EDAT 2026-09-08' }
];

const specialtyLabels: Record<string, Article['specialty']> = {
  rhinology: '鼻科', otology: '耳科', laryngology: '咽喉科', nasopharyngeal_carcinoma: '鼻咽癌'
};
const categoryLabels: Record<string, Article['category']> = {
  clinical: '临床研究', ai_ml: 'AI/ML', basic: '基础研究', review_meta: '综述 Meta', guideline_consensus: '指南共识'
};

function runtimeArticles(): Article[] | null {
  try {
    const configuredSnapshotDir = process.env.SNAPSHOT_DIR || '/data/snapshots';
    const snapshotDir = fs.existsSync(configuredSnapshotDir)
      ? configuredSnapshotDir
      : path.resolve(process.cwd(), '../data/snapshots');
    if (!fs.existsSync(snapshotDir)) return null;
    const snapshots = fs.readdirSync(snapshotDir)
      .filter((file: string) => /^daily-\d{4}-\d{2}-\d{2}\.json$/.test(file))
      .sort();
    if (!snapshots.length) return null;
    const records = new Map<string, any>();
    for (const snapshot of snapshots) {
      const payload = JSON.parse(fs.readFileSync(path.join(snapshotDir, snapshot), 'utf8'));
      for (const record of payload.articles || []) records.set(record.pmid, record);
    }
    const mapped = [...records.values()].flatMap((record: any): Article[] => {
      const model = record.classification;
      const specialty = specialtyLabels[record.primary_specialty || model?.primary_specialty];
      const category = categoryLabels[record.display_category || model?.display_category];
      if (!model || !specialty || !category) return [];
      const sources = Object.entries(record.source_dates || {}).map(([type, range]) => `${String(type).toUpperCase()} ${range}`).join('；');
      return [{
        pmid: record.pmid, specialty, category,
        evidenceTrack: (record.evidence_track || model.evidence_track) === 'basic_translational' ? '基础／转化' : '临床',
        journal: record.journal, publicationDate: record.publication_date || '日期未报告',
        jcr: record.jcr_quartile, fiveYearJif: record.five_year_jif,
        titleZh: model.title_zh, titleEn: record.title_en,
        authors: record.authors || [], affiliations: record.affiliations || [],
        abstractZh: model.abstract_zh, abstractEn: record.abstract_en,
        sourceDates: sources || 'EDAT 日期未报告',
        entryDate: String(record.source_dates?.edat || '').slice(0, 10) || undefined
      }];
    });
    return mapped;
  } catch {
    return null;
  }
}

export const articles: Article[] = runtimeArticles() ?? demoArticles;

export const specialties = ['全部', '鼻科', '耳科', '咽喉科', '鼻咽癌'];
export const categories = ['全部', '临床研究', '基础研究', 'AI/ML', '综述 Meta', '指南共识'];
