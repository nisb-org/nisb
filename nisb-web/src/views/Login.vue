<!-- /opt/mcp-gateway/nisb-web/src/views/Login.vue -->
<template>
  <div class="login-container">
    <div class="login-shell">
      <section class="login-brand">
        <div class="brand-chip">Self-hosted AI Workspace</div>
        <h1 class="title">NISB</h1>
        <p class="subtitle">Self-hosted AI Workspace</p>
        <p class="brand-copy">
          A private workspace for rooms, libraries, notes, RSS, evidence, and federated AI capabilities.
        </p>
      </section>

      <section class="login-box">
        <div class="login-header">
          <h2>Sign in</h2>
          <p>Continue to your NISB workspace.</p>
        </div>

        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <form class="auth-form" @submit.prevent="handleLogin">
          <div class="form-group">
            <label>Email</label>
            <input
              v-model="email"
              type="email"
              placeholder="your@email.com"
              autocomplete="email"
              required
            />
          </div>

          <div class="form-group">
            <label>Password</label>
            <input
              v-model="password"
              type="password"
              placeholder="Enter your password"
              autocomplete="current-password"
              required
            />
          </div>

          <button
            type="submit"
            class="login-btn"
            :disabled="loading"
          >
            {{ loading ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>

        <p class="register-link">
          New to NISB?
          <a href="#" @click.prevent="showRegister = true">Create an account</a>
        </p>
      </section>
    </div>

    <div v-if="showRegister" class="modal" @click.self="showRegister = false">
      <div class="modal-content" role="dialog" aria-modal="true" aria-label="Create account">
        <div class="modal-header">
          <div>
            <h2>Create account</h2>
            <p>Set up a new NISB workspace account.</p>
          </div>

          <button class="modal-x-btn" type="button" @click="showRegister = false" title="Close">
            ×
          </button>
        </div>

        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <form class="auth-form" @submit.prevent="handleRegister">
          <div class="form-group">
            <label>Username</label>
            <input
              v-model="registerData.username"
              type="text"
              placeholder="Username"
              autocomplete="username"
              required
            />
          </div>

          <div class="form-group">
            <label>Email</label>
            <input
              v-model="registerData.email"
              type="email"
              placeholder="your@email.com"
              autocomplete="email"
              required
            />
          </div>

          <div class="form-group">
            <label>Password</label>
            <input
              v-model="registerData.password"
              type="password"
              placeholder="At least 8 characters"
              autocomplete="new-password"
              required
              minlength="8"
            />
          </div>

          <button
            type="submit"
            class="register-btn"
            :disabled="registerLoading"
          >
            {{ registerLoading ? 'Creating account…' : 'Create account' }}
          </button>
        </form>

        <button class="close-btn" type="button" @click="showRegister = false">
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMCP } from '../composables/useMCP'
import { useSettingsStore } from '../stores/settings'

const router = useRouter()
const { callTool } = useMCP()
const settings = useSettingsStore()

settings.setRemoteLocaleSaver(async (payload) => {
  return await callTool('nisb_user_preferences_set', payload)
})

const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')

const showRegister = ref(false)
const registerData = ref({
  username: '',
  email: '',
  password: ''
})
const registerLoading = ref(false)

async function hydrateAccountLocaleAfterLogin() {
  try {
    await settings.hydrateRemoteLocalePreference(callTool)
  } catch (e) {}
}

async function handleLogin() {
  loading.value = true
  errorMessage.value = ''

  try {
    const result = await callTool('nisb_user_login', {
      email: email.value,
      password: password.value
    })

    if (result.status === 'success') {
      localStorage.setItem('nisb_token', result.token)
      localStorage.setItem('nisb_user_id', result.user_id)
      localStorage.setItem('nisb_username', result.username)

      await hydrateAccountLocaleAfterLogin()

      router.push('/editor')
    } else {
      errorMessage.value = result.message || 'Sign in failed.'
    }
  } catch (e) {
    errorMessage.value = e?.message || 'Sign in failed.'
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  registerLoading.value = true
  errorMessage.value = ''

  try {
    const result = await callTool('nisb_user_register', registerData.value)

    if (result.status === 'success') {
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: {
            message: 'Account created. Please sign in.',
            type: 'success'
          }
        })
      )
      showRegister.value = false
      email.value = registerData.value.email
      password.value = ''
    } else {
      errorMessage.value = result.message || 'Registration failed.'
    }
  } catch (e) {
    errorMessage.value = e?.message || 'Registration failed.'
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  width: 100vw;
  height: 100vh;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 18% 18%, rgba(84, 130, 197, 0.16), transparent 34%),
    radial-gradient(circle at 82% 12%, rgba(120, 160, 255, 0.12), transparent 28%),
    var(--editor-bg);
  color: var(--text-main);
}

.login-shell {
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 18px;
  align-items: stretch;
}

.login-brand,
.login-box {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.08);
}

.login-brand {
  padding: 34px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 420px;
}

.brand-chip {
  width: max-content;
  max-width: 100%;
  padding: 7px 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--selected-bg);
  color: var(--selected);
  font-size: 12.5px;
  font-weight: 650;
  margin-bottom: 18px;
}

.title {
  font-size: clamp(42px, 7vw, 72px);
  line-height: 0.95;
  color: var(--text-main);
  margin: 0 0 12px;
  letter-spacing: -0.055em;
}

.subtitle {
  color: var(--selected);
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 18px;
}

.brand-copy {
  max-width: 34rem;
  color: var(--text-secondary);
  font-size: 0.96rem;
  line-height: 1.65;
  margin: 0;
}

.login-box {
  padding: 26px;
}

.login-header {
  margin-bottom: 22px;
}

.login-header h2,
.modal-header h2 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.35rem;
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.login-header p,
.modal-header p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.45;
}

.error-message {
  padding: 10px 12px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  border-radius: 12px;
  margin-bottom: 14px;
  font-size: 0.88rem;
  line-height: 1.45;
}

.auth-form {
  display: grid;
  gap: 14px;
}

.form-group {
  display: grid;
  gap: 7px;
}

.form-group label {
  color: var(--text-main);
  font-size: 0.86rem;
  font-weight: 650;
}

.form-group input {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: var(--editor-bg);
  color: var(--text-main);
  font-size: 0.95rem;
  font-family: inherit;
  outline: none;
  transition:
    border-color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    box-shadow var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    background var(--transition-normal, 0.18s) var(--ease-smooth, ease);
}

.form-group input:focus {
  border-color: var(--selected);
  box-shadow: 0 0 0 3px rgba(80, 130, 255, 0.11);
}

.login-btn,
.register-btn,
.close-btn {
  width: 100%;
  height: 42px;
  padding: 0 14px;
  border-radius: 11px;
  font-size: 0.95rem;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  transition:
    background var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    border-color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    box-shadow var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    opacity var(--transition-normal, 0.18s) var(--ease-smooth, ease);
}

.login-btn,
.register-btn {
  margin-top: 4px;
  background: var(--selected);
  color: #fff;
  border: 1px solid var(--selected);
}

.login-btn:hover:not(:disabled),
.register-btn:hover:not(:disabled) {
  box-shadow: 0 0 0 3px rgba(80, 130, 255, 0.13);
}

.login-btn:disabled,
.register-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.register-link {
  text-align: center;
  margin: 18px 0 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.register-link a {
  color: var(--selected);
  font-weight: 700;
  text-decoration: none;
}

.register-link a:hover {
  text-decoration: underline;
}

.modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  padding: 20px;
  background: rgba(0, 0, 0, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  width: min(420px, 100%);
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--sidebar-bg);
  box-shadow: 0 24px 65px rgba(0, 0, 0, 0.24);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.modal-x-btn {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1.25rem;
  line-height: 1;
}

.modal-x-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.close-btn {
  margin-top: 12px;
  background: transparent;
  border: 1px solid var(--line);
  color: var(--text-secondary);
}

.close-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

@media (max-width: 760px) {
  .login-container {
    padding: 14px;
    align-items: flex-start;
    overflow: auto;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-brand {
    min-height: auto;
    padding: 24px;
  }

  .login-box {
    padding: 22px;
  }
}
</style>

