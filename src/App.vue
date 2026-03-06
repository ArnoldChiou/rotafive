<script setup>
import { useRouter } from 'vue-router';
import { store } from './store.js';
import { Layers, LogOut } from 'lucide-vue-next';

const router = useRouter();

const logout = () => {
  store.logout();
  router.push('/login');
};
</script>

<template>
  <div class="min-h-screen bg-slate-50 dark:bg-base-300 transition-colors duration-300 font-sans text-base-content flex flex-col">

    <!-- Navbar — only show when logged in -->
    <div v-if="store.token" class="navbar bg-base-100/80 backdrop-blur-md sticky top-0 z-50 border-b border-base-200">
      <div class="flex-1 px-2 lg:px-6">
        <router-link to="/" class="btn btn-ghost normal-case text-2xl font-black italic tracking-tighter gap-1 hover:bg-transparent px-0">
          <div class="bg-primary text-primary-content p-1.5 rounded-lg -rotate-6 shadow-md transition-transform hover:rotate-0">
            <Layers class="w-6 h-6"/>
          </div>
          <span class="bg-linear-to-r from-primary via-secondary to-accent bg-clip-text text-transparent">RotaFive</span>
        </router-link>
      </div>

      <div class="flex-none px-2 items-center gap-3">
        <!-- User Badge -->
        <div v-if="store.user" class="badge gap-1 font-medium"
          :class="store.user.role === 'client' ? 'badge-primary' : 'badge-secondary'">
          {{ store.user.role === 'client' ? '💼 Client' : '🧑‍💻 Freelancer' }}
        </div>

        <!-- Logout -->
        <button @click="logout" class="btn btn-ghost btn-sm gap-1">
          <LogOut class="w-4 h-4" /> Logout
        </button>
      </div>
    </div>

    <!-- Main Content — RouterView handles /login, /register, / -->
    <main class="grow relative overflow-x-hidden">
      <RouterView />
    </main>

    <!-- Footer — only show when logged in -->
    <footer v-if="store.token" class="footer footer-center p-6 bg-base-200 text-base-content/60 border-t border-base-300 mt-auto">
      <div>
        <p>RotaFive Prototype &copy; 2026 - Fair Dispatch Algorithm Demo</p>
      </div>
    </footer>
  </div>
</template>
