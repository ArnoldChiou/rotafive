<script setup>
import { computed, onMounted, onUnmounted } from 'vue';
import { store } from '../store.js';
import { Users, Clock, AlertCircle, CheckCircle2 } from 'lucide-vue-next';

// Auto-refresh the queue periodically to demonstrate real-time admin view
let intervalId;

onMounted(() => {
  store.fetchFreelancers();
  intervalId = setInterval(() => {
    store.fetchFreelancers();
  }, 5000);
});

onUnmounted(() => {
  clearInterval(intervalId);
});

// Sort freelancers to visualize the queue
// Highest priority (oldest lastAssignedAt + idle) are at the top
const queueList = computed(() => {
  return [...store.freelancers].sort((a, b) => {
    // Working people are not in the queue (or at the bottom)
    if (a.status === 'working' && b.status !== 'working') return 1;
    if (a.status !== 'working' && b.status === 'working') return -1;
    // Convert to timestamps if they are date strings from Postgres
    const timeA = new Date(a.last_assigned_at).getTime();
    const timeB = new Date(b.last_assigned_at).getTime();
    return timeA - timeB;
  });
});

const formatTime = (ts) => {
  if (!ts) return '-';
  const date = new Date(ts);
  // Postgres might return UTC timezone, adjust for local
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};
</script>

<template>
  <div class="p-4 md:p-8 w-full max-w-6xl mx-auto space-y-6">
    <div class="flex items-center gap-3 mb-6">
      <div class="p-3 bg-secondary/10 rounded-xl text-secondary">
        <Users class="w-8 h-8"/>
      </div>
      <div>
        <h2 class="text-3xl font-bold bg-linear-to-r from-secondary to-primary bg-clip-text text-transparent">Rotation Dashboard</h2>
        <p class="text-base-content/60 text-sm">Real-time view of the freelancer dispatch queue fairness system.</p>
      </div>
    </div>

    <div class="overflow-x-auto bg-base-100 shadow-xl rounded-box border border-base-300">
      <table class="table w-full table-zebra">
        <!-- head -->
        <thead class="bg-base-200 text-base-content/80 shadow-sm">
          <tr>
            <th class="w-16 text-center">Queue #</th>
            <th>Freelancer Profile</th>
            <th>Key Skills</th>
            <th class="text-center">Status</th>
            <th class="text-right">Last Dispatched</th>
          </tr>
        </thead>
        <TransitionGroup name="list" tag="tbody">
          <tr v-for="(f, index) in queueList" :key="f.id" :class="{'opacity-50 grayscale': f.status === 'working'}">
            <!-- Position Indicator -->
            <th class="text-center text-lg font-mono">
              <span v-if="f.status !== 'working'" class="badge badge-lg" :class="index < 5 ? 'badge-primary' : 'badge-ghost'">
                {{ index + 1 }}
              </span>
              <span v-else>-</span>
            </th>
            
            <!-- Profile -->
            <td>
              <div class="flex items-center gap-3">
                <div class="avatar placeholder">
                  <div class="bg-neutral text-neutral-content rounded-full w-10">
                    <span class="text-xs">{{ f.name.split(' ').map(n=>n[0]).join('') }}</span>
                  </div>
                </div>
                <div>
                  <div class="font-bold">{{ f.name }}</div>
                  <div class="text-xs opacity-50">⭐ {{ f.rating.toFixed(1) }}</div>
                </div>
              </div>
            </td>
            
            <!-- Skills -->
            <td>
              <div class="flex flex-wrap gap-1">
                <span v-for="s in f.skills" :key="s" class="badge badge-xs badge-outline">{{ s }}</span>
              </div>
            </td>
            
            <!-- Status -->
            <td class="text-center w-40">
               <div v-if="f.cooling" class="flex flex-col items-center gap-0.5">
                 <span class="badge badge-info gap-1 text-white text-xs">
                   <AlertCircle class="w-3 h-3 shrink-0"/> Cooling
                 </span>
                 <span class="text-xs text-base-content/50 font-mono">{{ Math.floor(f.cooldown_ttl / 60) }}m {{ f.cooldown_ttl % 60 }}s</span>
               </div>
               <span v-else-if="f.status === 'idle'" class="badge badge-success gap-1"><CheckCircle2 class="w-3 h-3"/> Idle</span>
               <span v-else-if="f.status === 'working'" class="badge badge-warning gap-1 animate-pulse"><Clock class="w-3 h-3"/> Working</span>
               <span v-else class="badge badge-neutral gap-1"><AlertCircle class="w-3 h-3"/> {{ f.status }}</span>
            </td>
            
            <!-- Time -->
            <td class="text-right font-mono text-sm">
              {{ formatTime(f.last_assigned_at) }}
            </td>
          </tr>
        </TransitionGroup>
      </table>
    </div>
  </div>
</template>

<style scoped>
.list-move,
.list-enter-active,
.list-leave-active {
  transition: all 0.5s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(30px) scale(0.95);
}
.list-leave-active {
  position: absolute;
}
</style>
