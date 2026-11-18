<template>
  <div class="oss-page">
    <div class="oss-shell">
      <router-link to="/" class="back-link">← 返回首页</router-link>

      <div class="oss-head">
        <div class="head-icon">🖼️</div>
        <div class="head-text">
          <h1>对象存储</h1>
          <p>打卡照片存进你自己的华为云 OBS 桶，服务端不托管任何图片</p>
        </div>
      </div>

      <!-- 当前状态 -->
      <a-card class="status-card" :bordered="false" :loading="loading && !config">
        <div v-if="config" class="status-row">
          <div class="status-main">
            <div class="status-title">
              <a-tag v-if="config.configured" color="green">已配置</a-tag>
              <a-tag v-else color="orange">尚未配置</a-tag>
              <span v-if="config.configured" class="bucket-name">{{ config.bucket }}</span>
            </div>
            <p v-if="config.configured" class="status-meta">
              {{ config.endpoint }} · Key：{{ config.ak_hint || '已保存' }}
            </p>
            <p v-else class="status-meta">
              配置好之后才能在足迹里上传打卡照片。照片直接进你的桶，站点既看不到也无法拷贝。
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
        <a-alert type="info" show-icon message="只有户主可以修改对象存储配置" />
        <p class="readonly-note">
          当前使用的是户主配置的桶，家庭成员共用。如需更换，请让户主在这里修改。
        </p>
      </a-card>

      <!-- 户主：编辑表单 -->
      <a-card v-else-if="config" class="form-card" :bordered="false">
        <a-form layout="vertical" :model="form">
          <a-form-item label="Endpoint" required>
            <a-input
              v-model:value="form.endpoint"
              placeholder="obs.cn-east-3.myhuaweicloud.com"
              allow-clear
            />
            <p class="field-hint">
              华为云控制台「对象存储服务 → 桶 → 概览」里的访问域名，不要带 https://
            </p>
          </a-form-item>

          <div class="form-grid">
            <a-form-item label="桶名（Bucket）" required>
              <a-input v-model:value="form.bucket" placeholder="trip-photos" allow-clear />
            </a-form-item>
            <a-form-item label="区域（可选）">
              <a-input v-model:value="form.region" placeholder="cn-east-3" allow-clear />
            </a-form-item>
          </div>

          <div class="form-grid">
            <a-form-item label="Access Key ID" :required="!config.configured">
              <a-input-password
                v-model:value="form.access_key_id"
                :placeholder="config.configured ? config.ak_hint || '已保存，留空不修改' : '华为云 AK'"
                autocomplete="off"
              />
            </a-form-item>
            <a-form-item label="Secret Access Key" :required="!config.configured">
              <a-input-password
                v-model:value="form.secret_access_key"
                :placeholder="config.configured ? config.sk_hint || '已保存，留空不修改' : '华为云 SK'"
                autocomplete="off"
              />
            </a-form-item>
          </div>

          <div class="form-grid">
            <a-form-item label="路径前缀">
              <a-input v-model:value="form.prefix" placeholder="footprint" allow-clear />
              <p class="field-hint">对象会存成 footprint/家庭ID/年/月/xxx.jpg</p>
            </a-form-item>
            <a-form-item label="访问域名（可选）">
              <a-input
                v-model:value="form.public_domain"
                placeholder="cdn.example.com"
                allow-clear
              />
              <p class="field-hint">配了 CDN 就填这里，图片地址会用它替换默认域名</p>
            </a-form-item>
          </div>

          <a-alert
            type="warning"
            show-icon
            class="tip"
            message="桶权限建议设为「公共读」"
          >
            <template #description>
              打卡图片要直接显示在页面上，如果桶是私有的，链接会 403。另一种做法是在 OBS 上挂
              CDN 域名，然后填到上面的「访问域名」里。AK/SK 建议用子账号，只授予这个桶的读写权限。
            </template>
          </a-alert>

          <div class="actions">
            <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
            <a-button :loading="testing" @click="handleTest">测试连接</a-button>
            <a-popconfirm
              v-if="config.configured"
              title="删除后打卡图片将无法上传，已上传的图不受影响。确定删除？"
              ok-text="删除"
              cancel-text="取消"
              @confirm="handleDelete"
            >
              <a-button danger :loading="deleting">删除配置</a-button>
            </a-popconfirm>
          </div>
        </a-form>
      </a-card>

      <a-card class="help-card" :bordered="false">
        <h3>怎么拿到这些值</h3>
        <ol class="help-list">
          <li>华为云控制台搜索「对象存储服务 OBS」，创建一个桶（区域建议选离你近的）。</li>
          <li>在「我的凭证 → 访问密钥」里新建 AK/SK，这一对就是上面的两个密码。</li>
          <li>把桶的「桶策略」设为公共读，图片才能直接在网页里打开。</li>
          <li>回到这里填 Endpoint 和桶名，点「测试连接」——会真传一张测试文件再删掉。</li>
        </ol>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  deleteOssConfig,
  fetchOssConfig,
  saveOssConfig,
  testOssConfig
} from '@/services/oss'
import type { OssConfig } from '@/types'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const deleting = ref(false)

const config = ref<OssConfig | null>(null)
const isOwner = ref(false)

const form = reactive({
  endpoint: '',
  bucket: '',
  region: '',
  access_key_id: '',
  secret_access_key: '',
  prefix: 'footprint',
  public_domain: ''
})

function formatTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
}

function fillForm(data: OssConfig): void {
  form.endpoint = data.endpoint || ''
  form.bucket = data.bucket || ''
  form.region = data.region || ''
  form.prefix = data.prefix || 'footprint'
  form.public_domain = data.public_domain || ''
  // 已存的 AK/SK 不回传明文，留空表示不修改
  form.access_key_id = ''
  form.secret_access_key = ''
}

async function loadConfig(): Promise<void> {
  loading.value = true
  try {
    const data = await fetchOssConfig()
    config.value = data
    isOwner.value = data.is_owner
    fillForm(data)
  } catch (e: any) {
    message.error(e?.message || '加载对象存储配置失败')
  } finally {
    loading.value = false
  }
}

function validate(): boolean {
  if (!form.endpoint.trim()) {
    message.warning('请填写 Endpoint')
    return false
  }
  if (!form.bucket.trim()) {
    message.warning('请填写桶名')
    return false
  }
  if (!config.value?.configured && !form.access_key_id.trim()) {
    message.warning('请填写 Access Key ID')
    return false
  }
  if (!config.value?.configured && !form.secret_access_key.trim()) {
    message.warning('请填写 Secret Access Key')
    return false
  }
  return true
}

function payload() {
  return {
    endpoint: form.endpoint.trim(),
    bucket: form.bucket.trim(),
    region: form.region.trim(),
    prefix: form.prefix.trim() || 'footprint',
    public_domain: form.public_domain.trim(),
    access_key_id: form.access_key_id.trim(),
    secret_access_key: form.secret_access_key.trim()
  }
}

async function handleSave(): Promise<void> {
  if (!validate()) return
  saving.value = true
  try {
    const data = await saveOssConfig(payload())
    config.value = data
    fillForm(data)
    message.success('已保存，可以在足迹里上传打卡照片了')
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest(): Promise<void> {
  if (!form.endpoint.trim() || !form.bucket.trim()) {
    message.warning('先填好 Endpoint 和桶名')
    return
  }
  testing.value = true
  try {
    const result = await testOssConfig(payload())
    message.success(`连接成功，耗时 ${result.latency_ms} ms`)
    const data = await fetchOssConfig()
    config.value = data
    fillForm(data)
  } catch (e: any) {
    message.error(e?.message || '连接测试失败')
  } finally {
    testing.value = false
  }
}

async function handleDelete(): Promise<void> {
  deleting.value = true
  try {
    const data = await deleteOssConfig()
    config.value = data
    fillForm(data)
    message.success('已删除配置')
  } catch (e: any) {
    message.error(e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.oss-page {
  min-height: calc(100vh - 64px);
  margin: -24px;
  padding: 40px 20px 64px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.oss-shell {
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

.oss-head {
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
.form-card,
.help-card {
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

.bucket-name {
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #9aa6b6;
  line-height: 1.6;
}

.tip {
  margin: 4px 0 18px;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.help-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #1f2d3d;
}

.help-list {
  margin: 0;
  padding-left: 20px;
  color: #5b6b7c;
  font-size: 13px;
  line-height: 2;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
