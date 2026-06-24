import { defineStore } from 'pinia'

const LS_KEY = 'nisb_agent_config_v1'

function safeParse(jsonText) {
  try {
    const v = JSON.parse(jsonText)
    return v && typeof v === 'object' ? v : null
  } catch (e) {
    return null
  }
}

export const useAgentConfigStore = defineStore('agentConfig', {
  state: () => ({
    enabled: false,
    plannerModel: 'gpt-4o-mini',
    maxSteps: 3,
    debug: false,
    plannerProvider: 'openai', // ✅ 保留：你现有字段

    // ✅ 新增：最终回答是否强制使用 Planner 模型（默认 false，绝不改变旧行为）
    // 仅推荐对 Off/Web 生效（具体由后端 orchestrator 控制）
    answerUsePlanner: false,

    _hydrated: false,
  }),

  actions: {
    hydrate() {
      if (this._hydrated) return
      this._hydrated = true

      const raw = localStorage.getItem(LS_KEY)
      if (!raw) return

      const saved = safeParse(raw)
      if (!saved) return

      if (typeof saved.enabled === 'boolean') this.enabled = saved.enabled
      if (typeof saved.plannerModel === 'string' && saved.plannerModel.trim()) this.plannerModel = saved.plannerModel.trim()
      if (typeof saved.maxSteps === 'number') this.maxSteps = Math.max(0, Math.min(8, Math.floor(saved.maxSteps)))
      if (typeof saved.debug === 'boolean') this.debug = saved.debug

      if (typeof saved.plannerProvider === 'string' && saved.plannerProvider.trim()) {
        this.plannerProvider = saved.plannerProvider.trim()
      }

      // ✅ 新字段：兼容旧存档（没有就保持默认 false）
      if (typeof saved.answerUsePlanner === 'boolean') {
        this.answerUsePlanner = saved.answerUsePlanner
      }
    },

    _persist() {
      const data = {
        enabled: !!this.enabled,
        plannerModel: String(this.plannerModel || 'gpt-4o-mini'),
        maxSteps: Math.max(0, Math.min(8, Math.floor(Number(this.maxSteps) || 0))),
        debug: !!this.debug,
        plannerProvider: String(this.plannerProvider || 'openai'),

        // ✅ 新字段：写入
        answerUsePlanner: !!this.answerUsePlanner,
      }
      localStorage.setItem(LS_KEY, JSON.stringify(data))
    },

    setEnabled(v) { this.enabled = !!v; this._persist() },
    setPlannerModel(v) { this.plannerModel = String(v || 'gpt-4o-mini'); this._persist() },
    setMaxSteps(v) { this.maxSteps = Math.max(0, Math.min(8, Math.floor(Number(v) || 0))); this._persist() },
    setDebug(v) { this.debug = !!v; this._persist() },

    setPlannerProvider(v) {
      this.plannerProvider = String(v || 'openai')
      this._persist()
    },

    // ✅ 新增 setter
    setAnswerUsePlanner(v) {
      this.answerUsePlanner = !!v
      this._persist()
    },
  },
})

