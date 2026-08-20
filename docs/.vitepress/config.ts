import { defineConfig } from 'vitepress'

// GitHub Pages 项目站点基路径：https://<user>.github.io/<repo>/
// 本地预览若需根路径，可临时 `DOCS_BASE=/ npm run docs:dev`。
const base = process.env.DOCS_BASE ?? '/AgriPolicy-Sandbox/'

const repo = 'https://github.com/Maicarons/AgriPolicy-Sandbox'

export default defineConfig({
  base,
  title: 'AgriPolicy Sandbox 文档',
  description: '基于 AgentSociety² 的农业政策反事实模拟沙盒 · 项目文档',
  lang: 'zh-CN',
  lastUpdated: true,
  cleanUrls: true,
  appearance: 'dark',
  themeConfig: {
    nav: [
      { text: '指南', link: '/guide/getting-started' },
      { text: '概念', link: '/concepts/architecture' },
      { text: '方法论', link: '/methodology/' },
      { text: 'API', link: '/api/economics' },
      { text: 'GitHub', link: repo },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '指南',
          items: [
            { text: '快速开始', link: '/guide/getting-started' },
            { text: '配置说明', link: '/guide/configuration' },
            { text: '运行实验', link: '/guide/running-experiments' },
            { text: '实验可视化 Web', link: '/guide/webview' },
            { text: '回放分析', link: '/guide/analysis' },
          ],
        },
      ],
      '/concepts/': [
        {
          text: '核心概念',
          items: [
            { text: '整体架构', link: '/concepts/architecture' },
            { text: '农户智能体 FarmerAgent', link: '/concepts/farmer-agent' },
            { text: '政策环境 AgriPolicyEnv', link: '/concepts/policy-environment' },
            { text: '经济核算模型', link: '/concepts/economics-model' },
            { text: '政策情景与反事实', link: '/concepts/policy-scenarios' },
          ],
        },
      ],
      '/methodology/': [
        {
          text: '研究方法',
          items: [
            { text: '总览', link: '/methodology/' },
            { text: '研究问题与假设', link: '/methodology/research-questions' },
            { text: '实验设计', link: '/methodology/experimental-design' },
            { text: '识别策略', link: '/methodology/identification' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 参考',
          items: [
            { text: '经济核算 economics', link: '/api/economics' },
            { text: '环境工具 env tools', link: '/api/env-tools' },
            { text: '命令行 CLI', link: '/api/cli' },
            { text: '回放数据表', link: '/api/data-schema' },
          ],
        },
      ],
      '/reference/': [
        {
          text: '参考',
          items: [
            { text: '贡献指南', link: '/reference/contributing' },
            { text: '许可与免责', link: '/reference/license-disclaimer' },
          ],
        },
      ],
    },
    socialLinks: [{ icon: 'github', link: repo }],
    search: { provider: 'local' },
    editLink: {
      pattern: `${repo}/edit/main/docs/:path`,
      text: '在 GitHub 上编辑此页',
    },
    docFooter: { prev: '上一篇', next: '下一篇' },
    outline: { label: '本页目录', level: [2, 3] },
    lastUpdatedText: '最后更新于',
    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '切换主题',
    lightModeSwitchTitle: '切换到浅色',
    darkModeSwitchTitle: '切换到深色',
    footer: {
      message: '基于 AgentSociety² 构建 · 仅供科研沙盒原型用途，经济学参数为示意值',
      copyright: 'Copyright © 2026 AgriPolicy-Sandbox 作者',
    },
  },
})
