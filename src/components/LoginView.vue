<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { store } from '../store.js';
import { LogIn, Mail, Lock, AlertCircle } from 'lucide-vue-next';

const router = useRouter();
const email = ref('');
const password = ref('');
const error = ref('');
const loading = ref(false);

const handleLogin = async () => {
  error.value = '';
  loading.value = true;
  const success = await store.login(email.value, password.value);
  loading.value = false;
  if (success) {
    router.push('/');
  } else {
    error.value = 'Invalid email or password.';
  }
};
</script>

<template>
  <div class="min-h-screen bg-base-200 flex items-center justify-center p-4">
    <div class="card w-full max-w-md bg-base-100 shadow-2xl border border-base-200">
      <div class="card-body p-8">
        <!-- Header -->
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-2xl mb-4">
            <LogIn class="w-8 h-8 text-primary" />
          </div>
          <h1 class="text-3xl font-black bg-linear-to-r from-primary to-secondary bg-clip-text text-transparent">RotaFive</h1>
          <p class="text-base-content/60 mt-1">Sign in to continue</p>
        </div>

        <!-- Error -->
        <div v-if="error" class="alert alert-error mb-4">
          <AlertCircle class="w-4 h-4" />
          <span>{{ error }}</span>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div class="form-control">
            <label class="label"><span class="label-text font-medium">Email</span></label>
            <label class="input input-bordered flex items-center gap-2">
              <Mail class="w-4 h-4 opacity-50" />
              <input v-model="email" type="email" placeholder="you@example.com" required class="grow" />
            </label>
          </div>

          <div class="form-control">
            <label class="label"><span class="label-text font-medium">Password</span></label>
            <label class="input input-bordered flex items-center gap-2">
              <Lock class="w-4 h-4 opacity-50" />
              <input v-model="password" type="password" placeholder="••••••••" required class="grow" />
            </label>
          </div>

          <button type="submit" class="btn btn-primary w-full mt-2" :disabled="loading">
            <span v-if="loading" class="loading loading-spinner loading-sm"></span>
            <span v-else>Sign In</span>
          </button>
        </form>

        <div class="divider text-base-content/40 text-sm">Don't have an account?</div>
        <router-link to="/register" class="btn btn-ghost w-full">Create Account</router-link>
      </div>
    </div>
  </div>
</template>
