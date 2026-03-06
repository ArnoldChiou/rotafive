<script setup>
import { ref } from 'vue';
import ClientView from './ClientView.vue';
import QueueView from './QueueView.vue';
import FreelancerSimulationView from './FreelancerSimulationView.vue';
import { store } from '../store.js';

const activeView = ref(store.user?.role === 'freelancer' ? 'freelancer' : 'client');
</script>

<template>
  <!-- Tabs only show views allowed for the current role -->
  <div class="flex gap-2 px-4 pt-4 max-w-5xl mx-auto" v-if="store.user?.role !== 'freelancer'">
    <button @click="activeView = 'client'" class="btn btn-sm" :class="activeView === 'client' ? 'btn-primary' : 'btn-ghost'">
      Client Match
    </button>
    <button @click="activeView = 'queue'" class="btn btn-sm" :class="activeView === 'queue' ? 'btn-secondary' : 'btn-ghost'">
      Rotation Queue
    </button>
  </div>

  <Transition name="fade-slide" mode="out-in">
    <ClientView v-if="activeView === 'client'" key="client" />
    <QueueView v-else-if="activeView === 'queue'" key="queue" />
    <FreelancerSimulationView v-else-if="activeView === 'freelancer'" key="freelancer" />
  </Transition>
</template>

<style>
.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.fade-slide-enter-from { opacity: 0; transform: translateX(-20px); }
.fade-slide-leave-to   { opacity: 0; transform: translateX(20px); }
</style>
