<template>
  <div class="app-shell">
    <header class="hero">
      <div>
        <h1>Project Phoenix</h1>
        <p>AI 面试助手（Agent 化求职辅助系统）</p>
      </div>
      <label class="user-input">
        用户名
        <input v-model.trim="username" placeholder="demo_user" />
      </label>
    </header>

    <nav class="tab-row">
      <button :class="{ active: tab === 'jd' }" @click="tab = 'jd'">岗位分析</button>
      <button :class="{ active: tab === 'resume' }" @click="tab = 'resume'">简历优化</button>
      <button :class="{ active: tab === 'interview' }" @click="tab = 'interview'">模拟面试</button>
    </nav>

    <main class="panel">
      <section v-if="tab === 'jd'" class="card">
        <h2>JD Analysis</h2>
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
        <label>关联 JD 会话ID（默认使用最近一次岗位分析会话）</label>
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
  </div>
</template>

<script setup>
import axios from "axios";
import { nextTick, ref } from "vue";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120000,
});

const username = ref("demo_user");
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
- 负责基于 Django/DRF 构建高可用后端服务，支撑 AI Agent 产品能力。
- 负责设计并实现 RAG 检索流程，包括向量化、召回与结果重排。
- 负责 MySQL、Redis 的性能优化，保障高并发下系统稳定性。
任职要求：
- 熟悉 Python，3 年以上后端经验。
- 熟悉 Django/DRF、MySQL、Redis、Docker。
- 有 OpenAI/DeepSeek API 或 Agent 项目经验。`;

const sampleResume = `工作经历：
- 使用 Django + DRF 开发内部系统，负责 30+ API 设计与实现。
- 优化 MySQL 查询和 Redis 缓存，接口平均响应时延下降 35%。
- 通过 Docker 搭建测试环境，提升团队联调效率。
项目经历：
- 智能问答系统：接入 OpenAI API，使用 FAISS 管理向量索引。`;

function pretty(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function extractError(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback;
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
    const { data } = await api.post("/jd/analyze", {
      username: username.value,
      jd_text: jdText.value,
    });
    jdSessionId.value = data.session_id;
    resumeSessionId.value = data.session_id;
    jdResult.value = data.message;
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
    const { data } = await api.post("/resume/optimize", {
      username: username.value,
      session_id: resumeSessionId.value,
      resume_text: resumeText.value,
    });
    resumeResult.value = data;
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
    const { data } = await api.post("/interview/chat", {
      username: username.value,
      topic: interviewTopic.value,
    });
    interviewSessionId.value = data.session_id;
    interviewMessages.value = [data.message];
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
    const { data } = await api.post("/interview/chat", {
      username: username.value,
      session_id: interviewSessionId.value,
      user_answer: answer,
    });
    interviewMessages.value.push(data.message);
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