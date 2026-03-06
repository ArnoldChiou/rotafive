<script setup>
import { ref } from 'vue';
import ClientView from './components/ClientView.vue';
import QueueView from './components/QueueView.vue';
import FreelancerSimulationView from './components/FreelancerSimulationView.vue';
import { Layers, Briefcase, Users, Mail } from 'lucide-vue-next';

// View toggle state
const activeView = ref('client'); // 'client' or 'queue'

</script>

<template>
  <div class="min-h-screen bg-slate-50 dark:bg-base-300 transition-colors duration-300 font-sans text-base-content flex flex-col">
    
    <!-- Navigation Bar -->
    <div class="navbar bg-base-100/80 backdrop-blur-md sticky top-0 z-50 border-b border-base-200">
      <div class="flex-1 px-2 lg:px-6">
        <a class="btn btn-ghost normal-case text-2xl font-black italic tracking-tighter gap-1 hover:bg-transparent px-0">
          <!-- Logo Icon -->
          <div class="bg-primary text-primary-content p-1.5 rounded-lg -rotate-6 shadow-md transition-transform hover:rotate-0">
             <Layers class="w-6 h-6"/>
          </div>
          <span class="bg-linear-to-r from-primary via-secondary to-accent bg-clip-text text-transparent">RotaFive</span>
        </a>
      </div>
      <div class="flex-none px-2 space-x-2">
        <!-- Toggles -->
        <button 
          @click="activeView = 'client'" 
          class="btn btn-sm md:btn-md border-none transition-all"
          :class="activeView === 'client' ? 'btn-primary shadow-lg shadow-primary/20 scale-105' : 'btn-ghost hover:bg-base-200 text-base-content/70'"
        >
          <Briefcase class="w-4 h-4 md:mr-1"/> <span class="hidden md:inline">Client Match</span>
        </button>
        <button 
          @click="activeView = 'queue'" 
          class="btn btn-sm md:btn-md border-none transition-all"
          :class="activeView === 'queue' ? 'btn-secondary shadow-lg shadow-secondary/20 scale-105' : 'btn-ghost hover:bg-base-200 text-base-content/70'"
        >
          <Users class="w-4 h-4 md:mr-1"/> <span class="hidden md:inline">Rotation Queue (Admin)</span>
        </button>
        <button 
          @click="activeView = 'freelancer'" 
          class="btn btn-sm md:btn-md border-none transition-all"
          :class="activeView === 'freelancer' ? 'btn-accent shadow-lg shadow-accent/20 scale-105 text-white' : 'btn-ghost hover:bg-base-200 text-base-content/70'"
        >
          <Mail class="w-4 h-4 md:mr-1"/> <span class="hidden md:inline">Freelancer Mock</span>
        </button>
      </div>
    </div>

    <!-- Main Content Area with Transition -->
    <main class="grow relative overflow-x-hidden">
      <!-- Vue <Transition> requires activeView items to have keys for mode="out-in" -->
      <Transition name="fade-slide" mode="out-in">
        <ClientView v-if="activeView === 'client'" key="client" />
        <QueueView v-else-if="activeView === 'queue'" key="queue" />
        <FreelancerSimulationView v-else-if="activeView === 'freelancer'" key="freelancer" />
      </Transition>
    </main>

    <!-- Footer -->
    <footer class="footer footer-center p-6 bg-base-200 text-base-content/60 border-t border-base-300 mt-auto">
      <div>
        <p>RotaFive Prototype &copy; 2026 - Fair Dispatch Algorithm Demo</p>
      </div>
    </footer>
  </div>
</template>

<style>
/* Global Transition Definition */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
