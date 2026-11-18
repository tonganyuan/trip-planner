<template>
  <div class="model-page">
    <div class="model-shell">
      <router-link to="/" class="back-link">← 返回首页</router-link>

      <div class="model-head">
        <div class="head-icon">🤖</div>
        <div class="head-text">
          <h1>模型设置</h1>
          <p>每个家庭用自己的大模型额度，互不影响</p>
        </div>
      </div>

      <!-- 当前状态 -->
      <a-card class="status-card" :bordered="false" :loading="loading && !config">
        <div v-if="config" class="status-row">
          <div class="status-main">
            <div class="status-title">
              <a-tag v-if="config.configured" color="green">已配置</a-tag>
              <a-tag v-else color="orange">尚未配置</a-tag>
              <span v-if="config.configured" class="model-name">{{ config.model }}</span>
            </div>
            <p v-if="config.configured" class="status-meta">
              {{ config.base_url }} · Key：{{ config.api_key_hint || '已保存' }}
            </p>
            <p v-else class="status-meta">
              配置好之后才能生成行程。你填的 Key 只用于你自己的家庭，站点不会拿它给别人用。
            </p>
            <p v-if="config.configured" class="status-meta dim">
              {{ config.updated_by_name ? `${config.updated_by_name} 于 ` : '' }}{{ formatTime(config.updated_at) }} 修改
              <template v-if="config.verified_at"> · {{ formatTime(config.verified_at) }} 验证通过</template>
            </p>
          </div>
          <a-button v-if="config.configured" size="small" :loading="testing" @click="handleTest">
            测试连接
          </a-button>
        </div>
      </a-card>

      <!-- 非户主：只读 -->
      <a-card v-if="config && !isOwner" class="form-card" :bordered="false">
        <a-alert type="info" show-icon :message="'只有户主可以修改模型配置'" />
        <p class="readonly-note">
          当前模型由户主设置，家庭成员共用。如需更换，请让户主在「模型设置」里修改。
        </p>
      </a-card>

      <!-- 户主：编辑表单 -->
      <a-card v-else-if="config" class="form-card" :bordered="false">
        <a-form layout="vertical" :model="form">
          <a-form-item label="选择服务商（可一键填好地址与模型）">
            <div class="preset-grid">
              <button
                v-for="p in presets"
                :key="p.id"
                type="button"
                class="preset-item"
                :class="{ active: form.provider === p.id }"
                @click="applyPreset(p)"
              >
                <span class="preset-label">{{ p.label }}</span>
                <span class="preset-note">{{ p.note }}</span>
              </button>
            </div>
          </a-form-item>

          <a-form-item label="服务地址（Base URL）" required>
            <a-input
              v-model:value="form.base_url"
              placeholder="https://api.deepseek.com"
              allow-clear
            />
            <div class="field-hint">
              需兼容 OpenAI 的 /chat/completions 接口。也可以指向自建的 vLLM / Ollama。
            </div>
          </a-form-item>

          <a-form-item label="模型名称" required>
            <a-input v-model:value="form.model" placeholder="deepseek-chat" allow-clear />
            <div v-if="currentPreset?.doc_url" class="field-hint">
              在
              <a :href="currentPreset.doc_url" target="_blank" rel="noopener">{{ currentPreset.label }}</a>
              控制台可以查看可用模型与创建 Key
            </div>
          </a-form-item>

          <a-form-item label="API Key" required>
            <a-input-password
              v-model:value="form.api_key"
              :placeholder="config.configured ? `已保存 ${config.api_key_hint}，留空则不修改` : '粘贴你的 API Key'"
              autocomplete="new-password"
            />
            <div class="field-hint">
              加密后存在服务器上（AES-GCM），接口永远不会把明文回传到浏览器；
              页面上只显示前 3 位和后 4 位。
            </div>
          </a-form-item>

          <a-form-item>
            <template #label>
              <span>温度 temperature</span>
              <span class="temp-value">{{ form.temperature.toFixed(1) }}</span>
            </template>
            <a-slider v-model:value="form.temperature" :min="0" :max="1.5" :step="0.1" />
            <div class="field-hint">越低越稳定、越高越发散。行程规划建议 0.5 ~ 0.7。</div>
          </a-form-item>

          <div class="actions">
            <a-button type="primary" :loading="saving" @click="handleSave">保存配置</a-button>
            <a-button :loading="testing" @click="handleTest">测试连接</a-button>
            <a-popconfirm
              v-if="config.configured"
              title="删除后该家庭将无法生成行程，确认删除？"
              ok-text="删除"
              cancel-text="取消"
              @confirm="handleDelete"
            >
              <a-button danger type="text" :loading="deleting">删除配置</a-button>
            </a-popconfirm>
          </div>

          <div v-if="testResult" class="test-result" :class="{ fail: !testResult.success }">
            <span class="test-icon">{{ testResult.success ? '✅' : '⚠️' }}</span>
            <div class="test-body">
              <div class="test-title">
                {{ testResult.message }}
                <span v-if="testResult.success" class="test-latency">{{ testResult.latency_ms }} ms</span>
              </div>
              <div v-if="testResult.success && testResult.reply" class="test-reply">
                模型回复：{{ testResult.reply }}
              </div>
            </div>
          </div>
        </a-form>
      </a-card>

      <p class="footnote">
        🔐 服务端只保存密文，解密密钥由 AUTH_SECRET 派生、不与数据库同处；
        即便如此，也建议给 Key 设置限额，避免意外消耗。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  deleteLlmConfig,
  fetchLlmConfig,
  saveLlmConfig,
  testLlmConfig
} from '@/services/llmConfig'
import type { LlmConfig, LlmPreset, LlmTestResponse } from '@/types'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const deleting = ref(false)

const config = ref<LlmConfig | null>(null)
const isOwner = ref(false)
const presets = ref<LlmPreset[]>([])
const testResult = ref<LlmTestResponse | null>(null)

const form = reactive({
  provider: 'deepseek',
  base_url: '',
  model: '',
  api_key: '',
  temperature: 0.7
})

const currentPreset = computed(() => presets.value.find((p) => p.id === form.provider))

function formatTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
}

function fillForm(data: LlmConfig): void {
  form.provider = data.provider || 'custom'
  form.base_url = data.base_url || ''
  form.model = data.model || ''
  form.temperature = data.temperature ?? 0.7
  // 已保存的 Key 不回传明文，留空表示不修改
  form.api_key = ''
}

async function loadConfig(): Promise<void> {
  loading.value = true
  try {
    const data = await fetchLlmConfig()
    config.value = data.config
    isOwner.value = data.is_owner
    presets.value = data.presets || []
    fillForm(data.config)
  } catch (e: any) {
    message.error(e?.message || '加载模型配置失败')
  } finally {
    loading.value = false
  }
}

function applyPreset(preset: LlmPreset): void {
  form.provider = preset.id
  if (preset.id !== 'custom') {
    form.base_url = preset.base_url
    form.model = preset.model
  }
  testResult.value = null
}

async function handleSave(): Promise<void> {
  if (!form.base_url.trim()) {
    message.warning('请填写服务地址')
    return
  }
  if (!form.model.trim()) {
    message.warning('请填写模型名称')
    return
  }
  if (!config.value?.configured && !form.api_key.trim()) {
    message.warning('请填写 API Key')
    return
  }
  saving.value = true
  try {
    const data = await saveLlmConfig({
      provider: form.provider,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      api_key: form.api_key.trim(),
      temperature: form.temperature
    })
    config.value = data.config
    isOwner.value = data.is_owner
    presets.value = data.presets || []
    fillForm(data.config)
    message.success('已保存，生成行程时会使用这个模型')
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest(): Promise<void> {
  if (!form.base_url.trim() || !form.model.trim()) {
    message.warning('先填好服务地址和模型名称')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const result = await testLlmConfig({
      provider: form.provider,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      api_key: form.api_key.trim()
    })
    testResult.value = result
    message.success(`连接成功，耗时 ${result.latency_ms} ms`)
  } catch (e: any) {
    testResult.value = {
      success: false,
      message: e?.message || '连接失败',
      latency_ms: 0,
      reply: '',
      model: form.model,
      base_url: form.base_url
    }
    message.error(e?.message || '连接失败')
  } finally {
    testing.value = false
  }
}

async function handleDelete(): Promise<void> {
  deleting.value = true
  try {
    const data = await deleteLlmConfig()
    config.value = data.config
    presets.value = data.presets || []
    fillForm(data.config)
    testResult.value = null
    message.success('已删除模型配置')
  } catch (e: any) {
    message.error(e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.model-page {
  min-height: calc(100vh - 64px);
  margin: -24px;
  padding: 40px 20px 64px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.model-shell {
  max-width: 860px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 18px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  text-decoration: none;
}

.back-link:hover {
  color: #fff;
}

.model-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  color: #fff;
}

.head-icon {
  font-size: 46px;
  line-height: 1;
}

.head-text h1 {
  margin: 0;
  font-size: 30px;
}

.head-text p {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
}

.status-card,
.form-card {
  margin-bottom: 20px;
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.status-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.status-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.model-name {
  font-size: 17px;
  font-weight: 600;
  color: #1f2d3d;
}

.status-meta {
  margin: 8px 0 0;
  font-size: 13px;
  color: #5b6b7c;
  word-break: break-all;
}

.status-meta.dim {
  color: #94a3b8;
}

.readonly-note {
  margin: 14px 0 0;
  font-size: 13px;
  color: #5b6b7c;
  line-height: 1.7;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}

.preset-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  text-align: left;
  background: #f7f8fb;
  border: 1px solid #e6e8ef;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.preset-item:hover {
  border-color: #91b4f3;
  background: #f2f6ff;
}

.preset-item.active {
  border-color: #667eea;
  background: #eef2ff;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.16);
}

.preset-label {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}

.preset-note {
  font-size: 12px;
  color: #8a97a8;
  line-height: 1.5;
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #8a97a8;
  line-height: 1.6;
}

.temp-value {
  margin-left: 8px;
  font-weight: 600;
  color: #667eea;
}

.actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.test-result {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  padding: 12px 14px;
  background: #f0fbf3;
  border: 1px solid #b7ebc6;
  border-radius: 10px;
}

.test-result.fail {
  background: #fff5f5;
  border-color: #ffc9c9;
}

.test-icon {
  line-height: 1.4;
}

.test-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}

.test-latency {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: #7a8a9a;
}

.test-reply {
  margin-top: 4px;
  font-size: 13px;
  color: #5b6b7c;
}

.footnote {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.78);
}

@media (max-width: 768px) {
  .model-page {
    margin: 0;
    padding: 24px 14px 40px;
  }

  .model-head {
    gap: 12px;
  }

  .head-icon {
    font-size: 36px;
  }

  .head-text h1 {
    font-size: 22px;
  }

  .preset-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }
}
</style>
