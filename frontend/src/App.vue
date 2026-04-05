<template>
  <div class="app-shell">
    <header class="hero">
      <div>
        <p class="eyebrow">FastAPI + PostgreSQL + RabbitMQ</p>
        <h1>Project Phoenix</h1>
        <p>AI 面试助手，重构为异步任务驱动架构。</p>
      </div>

      <div v-if="isAuthenticated" class="auth-status">
        <span class="badge">当前用户：{{ currentUser?.username }}</span>
        <button @click="logout">退出登录</button>
      </div>
    </header>

    <section v-if="!isAuthenticated" class="panel auth-panel">
      <div class="card auth-card">
        <h2>认证</h2>
        <p>新版本使用 JWT 鉴权，先注册或登录后再发起岗位分析、简历优化和模拟面试。</p>

        <div class="auth-toggle">
          <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">登录</button>
          <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">注册</button>
        </div>

        <label>
          用户名
          <input v-model.trim="authUsername" placeholder="例如：demo_user" />
        </label>

        <label>
          密码
          <input v-model="authPassword" type="password" placeholder="至少 8 位" />
        </label>

        <div class="action-row">
          <button class="primary" :disabled="authLoading || !canSubmitAuth" @click="submitAuth">
            {{ authLoading ? "提交中..." : authMode === "login" ? "登录" : "注册并登录" }}
          </button>
        </div>

        <div v-if="authError" class="error">{{ authError }}</div>
      </div>
    </section>

    <template v-else>
      <nav class="tab-row">
        <button :class="{ active: tab === 'jd' }" @click="tab = 'jd'">岗位分析</button>
        <button :class="{ active: tab === 'resume' }" @click="tab = 'resume'">简历优化</button>
        <button :class="{ active: tab === 'interview' }" @click="tab = 'interview'">模拟面试</button>
      </nav>

      <main class="panel">
        <section v-if="tab === 'jd'" class="card">
          <h2>JD Analysis</h2>
          <p class="card-tip">提交后会进入 RabbitMQ 队列，前端自动轮询任务状态。</p>
          <textarea
            v-model="jdText"
            rows="10"
            placeholder="粘贴岗位描述..."
          ></textarea>
          <div class="action-row">
            <button @click="fillSampleJd">填充示例 JD</button>
            <button class="primary" :disabled="jdLoading || !jdText" @click="analyzeJd">
              {{ jdLoading ? "分析中..." : "开始分析" }}
            </button>
          </div>

          <div v-if="jdError" class="error">{{ jdError }}</div>
          <div v-if="jdResult" class="result-box">
            <p class="badge">会话ID：{{ jdSessionId }}</p>
            <pre>{{ jdResult.content }}</pre>
            <h3>结构化结果</h3>
            <pre>{{ pretty(jdResult.metadata) }}</pre>
          </div>
        </section>

        <section v-if="tab === 'resume'" class="card">
          <h2>Resume Optimization</h2>
          <label>关联 JD 会话ID</label>
          <input v-model.number="resumeSessionId" type="number" min="1" />

          <textarea
            v-model="resumeText"
            rows="10"
            placeholder="粘贴简历内容..."
          ></textarea>

          <div class="action-row">
            <button @click="fillSampleResume">填充示例简历</button>
            <button class="primary" :disabled="resumeLoading || !resumeText || !resumeSessionId" @click="optimizeResume">
              {{ resumeLoading ? "优化中..." : "开始优化" }}
            </button>
          </div>

          <div v-if="resumeError" class="error">{{ resumeError }}</div>
          <div v-if="resumeResult" class="result-box">
            <p class="badge">会话ID：{{ resumeResult.session_id }}</p>
            <pre>{{ resumeResult.message.content }}</pre>
            <h3>结构化结果</h3>
            <pre>{{ pretty(resumeResult.message.metadata) }}</pre>
          </div>
        </section>

        <section v-if="tab === 'interview'" class="card">
          <h2>Mock Interview</h2>
          <p class="card-tip">模拟面试也会走异步任务，避免长时间占用 Web 进程。</p>
          <div class="interview-start">
            <input v-model.trim="interviewTopic" placeholder="例如：Python后端" />
            <button class="primary" :disabled="interviewLoading || !interviewTopic" @click="startInterview">
              开始新面试
            </button>
          </div>

          <p v-if="interviewSessionId" class="badge">当前面试会话ID：{{ interviewSessionId }}</p>

          <div class="chat-box" ref="chatBox">
            <div
              v-for="(item, index) in interviewMessages"
              :key="index"
              :class="['bubble', item.role === 'assistant' ? 'assistant' : 'user']"
            >
              <strong>{{ item.role === "assistant" ? "AI面试官" : "你" }}</strong>
              <p>{{ item.content }}</p>
            </div>
          </div>

          <textarea
            v-model="interviewAnswer"
            rows="4"
            placeholder="输入你的回答..."
          ></textarea>
          <div class="action-row">
            <button
              class="primary"
              :disabled="interviewLoading || !interviewSessionId || !interviewAnswer"
              @click="sendInterviewAnswer"
            >
              {{ interviewLoading ? "发送中..." : "发送回答" }}
            </button>
          </div>

          <div v-if="interviewError" class="error">{{ interviewError }}</div>
        </section>
      </main>
    </template>
  </div>
</template>

<script setup>
import axios from "axios";
import { computed, nextTick, ref } from "vue";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

const savedToken = localStorage.getItem("phoenix_token") || "";
const savedUser = localStorage.getItem("phoenix_user");

const token = ref(savedToken);
const currentUser = ref(savedUser ? JSON.parse(savedUser) : null);
const authMode = ref("login");
const authUsername = ref("demo_user");
const authPassword = ref("demo_pass_123");
const authLoading = ref(false);
const authError = ref("");

const tab = ref("jd");

const jdText = ref("");
const jdLoading = ref(false);
const jdError = ref("");
const jdResult = ref(null);
const jdSessionId = ref(null);

const resumeText = ref("");
const resumeSessionId = ref(null);
const resumeLoading = ref(false);
const resumeError = ref("");
const resumeResult = ref(null);

const interviewTopic = ref("Python后端");
const interviewSessionId = ref(null);
const interviewMessages = ref([]);
const interviewAnswer = ref("");
const interviewLoading = ref(false);
const interviewError = ref("");
const chatBox = ref(null);

const sampleJd = `职位名称：Python 后端开发工程师（AI Agent方向）
岗位职责：
- 负责基于 FastAPI 构建高可用后端服务，支撑 AI Agent 产品能力。
- 负责设计并实现 PostgreSQL、Redis、RabbitMQ 的协同方案。
- 负责设计异步任务链路，保障高并发下系统稳定性。
任职要求：
- 熟悉 Python，3 年以上后端经验。
- 熟悉 FastAPI、PostgreSQL、Redis、RabbitMQ、Docker。
- 有 OpenAI/DeepSeek API 或 Agent 项目经验。`;

const sampleResume = `工作经历：
- 使用 Django + DRF 开发内部系统，负责 30+ API 设计与实现。
- 优化 MySQL 查询和 Redis 缓存，接口平均响应时延下降 35%。
- 通过 Docker 搭建测试环境，提升团队联调效率。
项目经历：
- 智能问答系统：接入 OpenAI API，使用 FAISS 管理向量索引。`;

api.interceptors.request.use((config) => {
  if (token.value) {
    config.headers.Authorization = `Bearer ${token.value}`;
  }
  return config;
});

const isAuthenticated = computed(() => Boolean(token.value && currentUser.value));
const canSubmitAuth = computed(() => authUsername.value.length >= 3 && authPassword.value.length >= 8);

function pretty(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function extractError(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("；");
  }
  return error?.message || fallback;
}

function persistAuth(data) {
  token.value = data.access_token;
  currentUser.value = data.user;
  localStorage.setItem("phoenix_token", data.access_token);
  localStorage.setItem("phoenix_user", JSON.stringify(data.user));
}

function logout() {
  token.value = "";
  currentUser.value = null;
  localStorage.removeItem("phoenix_token");
  localStorage.removeItem("phoenix_user");
}

async function submitAuth() {
  authLoading.value = true;
  authError.value = "";
  try {
    const path = authMode.value === "login" ? "/auth/login" : "/auth/register";
    const { data } = await api.post(path, {
      username: authUsername.value,
      password: authPassword.value,
    });
    persistAuth(data);
  } catch (error) {
    authError.value = extractError(error, "认证失败，请稍后重试。");
  } finally {
    authLoading.value = false;
  }
}

async function waitForJob(jobId, fallback) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const { data } = await api.get(`/jobs/${jobId}`);
    if (data.status === "succeeded") {
      return data;
    }
    if (data.status === "failed") {
      throw new Error(data.error || fallback);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("任务等待超时，请稍后查看任务状态。");
}

function fillSampleJd() {
  jdText.value = sampleJd;
}

function fillSampleResume() {
  resumeText.value = sampleResume;
}

async function analyzeJd() {
  jdLoading.value = true;
  jdError.value = "";
  try {
    const { data: submitted } = await api.post("/jd/analyze", {
      jd_text: jdText.value,
    });
    const job = await waitForJob(submitted.job_id, "JD 分析失败，请稍后重试。");
    jdSessionId.value = job.result.session_id;
    resumeSessionId.value = job.result.session_id;
    jdResult.value = job.result.message;
    tab.value = "resume";
  } catch (error) {
    jdError.value = extractError(error, "JD 分析失败，请稍后重试。");
  } finally {
    jdLoading.value = false;
  }
}

async function optimizeResume() {
  resumeLoading.value = true;
  resumeError.value = "";
  try {
    const { data: submitted } = await api.post("/resume/optimize", {
      session_id: resumeSessionId.value,
      resume_text: resumeText.value,
    });
    const job = await waitForJob(submitted.job_id, "简历优化失败，请稍后重试。");
    resumeResult.value = job.result;
  } catch (error) {
    resumeError.value = extractError(error, "简历优化失败，请稍后重试。");
  } finally {
    resumeLoading.value = false;
  }
}

async function startInterview() {
  interviewLoading.value = true;
  interviewError.value = "";
  try {
    const { data: submitted } = await api.post("/interview/chat", {
      topic: interviewTopic.value,
    });
    const job = await waitForJob(submitted.job_id, "启动模拟面试失败，请稍后重试。");
    interviewSessionId.value = job.result.session_id;
    interviewMessages.value = [job.result.message];
    tab.value = "interview";
    await scrollChatToBottom();
  } catch (error) {
    interviewError.value = extractError(error, "启动模拟面试失败，请稍后重试。");
  } finally {
    interviewLoading.value = false;
  }
}

async function sendInterviewAnswer() {
  if (!interviewAnswer.value) return;

  const answer = interviewAnswer.value;
  interviewMessages.value.push({ role: "user", content: answer });
  interviewAnswer.value = "";
  interviewLoading.value = true;
  interviewError.value = "";
  await scrollChatToBottom();

  try {
    const { data: submitted } = await api.post("/interview/chat", {
      session_id: interviewSessionId.value,
      user_answer: answer,
    });
    const job = await waitForJob(submitted.job_id, "发送回答失败，请稍后重试。");
    interviewMessages.value.push(job.result.message);
    await scrollChatToBottom();
  } catch (error) {
    interviewError.value = extractError(error, "发送回答失败，请稍后重试。");
  } finally {
    interviewLoading.value = false;
  }
}

async function scrollChatToBottom() {
  await nextTick();
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight;
  }
}
</script>
