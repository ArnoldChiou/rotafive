<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { store } from '../store.js';
import { Search, Loader2, Star, Briefcase, Zap, CheckCircle2, Mail } from 'lucide-vue-next';

const jobTitle = ref('');
const selectedSkills = ref([]);
const isSearching = ref(false);
const matchedCandidates = ref([]);
const matchComplete = ref(false);
const showSuccessMsg = ref(false);
const currentProjectId = ref(null);

const availableSkills = store.availableSkills;

const toggleSkill = (skill) => {
  if (selectedSkills.value.includes(skill)) {
    selectedSkills.value = selectedSkills.value.filter(s => s !== skill);
  } else {
    selectedSkills.value.push(skill);
  }
};

const findMatches = async () => {
  if (!jobTitle.value) {
    alert("Please enter a job title");
    return;
  }
  
  // Reset
  matchComplete.value = false;
  matchedCandidates.value = [];
  isSearching.value = true;
  
  try {
    const response = await store.getMatches(selectedSkills.value);
    
    // Fake delay for animation "Searching..."
    setTimeout(() => {
      currentProjectId.value = response.project_id;
      matchedCandidates.value = response.matches;
      isSearching.value = false;
      matchComplete.value = true;
    }, 1500);
  } catch (error) {
    console.error("Error finding matches", error);
    isSearching.value = false;
  }
};

const selectFreelancer = async (id) => {
  const success = await store.selectFreelancer(id, currentProjectId.value);
  if (success) {
    matchedCandidates.value = matchedCandidates.value.filter(c => c.id !== id);
    showSuccessMsg.value = true;
    setTimeout(() => showSuccessMsg.value = false, 3000);
  } else {
    alert("Failed to assign freelancer. Please try again.");
  }
};

const declineFreelancer = async (id) => {
  const newCandidate = await store.declineInvitation(id, currentProjectId.value);
  
  // Slide out the declined candidate
  matchedCandidates.value = matchedCandidates.value.filter(c => c.id !== id);
  
  if (newCandidate) {
    // New candidate comes in as uninvited
    newCandidate.status = 'idle';
    // Slide in the replacement candidate
    matchedCandidates.value.push(newCandidate);
  } else {
    alert("Warning: No more available freelancers in the queue to replace them.");
  }
};

const sendInvite = async (candidate) => {
  candidate.isInviting = true;
  const success = await store.inviteFreelancer(candidate.id, currentProjectId.value);
  candidate.isInviting = false;
  if (success) {
    candidate.status = 'invited';
  } else {
    alert("Failed to send invitation. They might already be invited.");
  }
};

// Handle real-time sync across tabs using BroadcastChannel
let syncChannel = null;

onMounted(() => {
  syncChannel = new BroadcastChannel('rotafive_sync');
  syncChannel.onmessage = (event) => {
    const data = event.data;
    
    // Only react if this event corresponds to our current project search
    if (data.projectId !== currentProjectId.value) return;

    if (data.type === 'DECLINED_REPLACED') {
      // Slide out the declined candidate
      matchedCandidates.value = matchedCandidates.value.filter(c => c.id !== data.declinedId);
      
      // Slide in the new candidate
      const newCand = data.replacement;
      newCand.status = 'idle'; // Because the backend no longer auto-invites them
      matchedCandidates.value.push(newCand);
    } 
    else if (data.type === 'DECLINED_NO_REPLACEMENT') {
      matchedCandidates.value = matchedCandidates.value.filter(c => c.id !== data.declinedId);
      alert("A freelancer declined, but there are no more available replacements in the queue.");
    }
    else if (data.type === 'ACCEPTED') {
      // The freelancer accepted, remove them from this view as they are now hired
      matchedCandidates.value = matchedCandidates.value.filter(c => c.id !== data.freelancerId);
      showSuccessMsg.value = true;
      setTimeout(() => showSuccessMsg.value = false, 3000);
    }
  };
});

onUnmounted(() => {
  if (syncChannel) {
    syncChannel.close();
  }
});
</script>

<template>
  <div class="px-4 py-8 md:py-12 w-full max-w-5xl mx-auto">
    <!-- Header / Context -->
    <div class="text-center mb-10">
      <h1 class="text-4xl md:text-5xl font-extrabold mb-4 bg-linear-to-r from-primary to-secondary bg-clip-text text-transparent">
        Post a Job, Get the Best Fit instantly.
      </h1>
      <p class="text-lg text-base-content/70 max-w-2xl mx-auto">
        No endless bidding. Our RotaFive algorithm finds 5 available experts instantly based on fair rotation.
      </p>
    </div>

    <!-- MAIN CARD -->
    <div class="card bg-base-100 shadow-2xl border border-base-200/50 backdrop-blur-sm relative overflow-hidden">
      <!-- Decorator Blob -->
      <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 rounded-full blur-3xl"></div>
      
      <div class="card-body">
        
        <div class="grid md:grid-cols-2 gap-8">
          <!-- Job Details -->
          <div class="space-y-4">
            <h3 class="text-xl font-bold flex items-center gap-2"><Briefcase class="w-5 h-5 text-primary"/> Project Details</h3>
            <div class="form-control w-full">
              <label class="label"><span class="label-text font-medium">Job Title</span></label>
              <input v-model="jobTitle" type="text" placeholder="e.g. Need a sleek Landing Page" class="input input-bordered w-full input-lg focus:border-primary focus:ring-1 focus:ring-primary" />
            </div>
          </div>
          
          <!-- Skills Selection -->
          <div class="space-y-4">
             <h3 class="text-xl font-bold flex items-center gap-2"><Zap class="w-5 h-5 text-secondary"/> Required Skills</h3>
             <label class="label"><span class="label-text font-medium">Select to filter (Leave empty for all)</span></label>
             <div class="flex flex-wrap gap-2 mt-2">
                <button 
                  v-for="skill in availableSkills" 
                  :key="skill"
                  @click="toggleSkill(skill)"
                  class="btn btn-sm rounded-full transition-all duration-300"
                  :class="selectedSkills.includes(skill) ? 'btn-secondary text-secondary-content border-secondary shadow-lg shadow-secondary/30' : 'btn-outline border-base-300 hover:border-secondary'"
                >
                  {{ skill }}
                  <CheckCircle2 v-if="selectedSkills.includes(skill)" class="w-3 h-3 ml-1"/>
                </button>
             </div>
          </div>
        </div>

        <div class="divider mt-8 mb-6"></div>

        <div class="flex justify-center">
          <button 
            @click="findMatches" 
            class="btn btn-primary btn-lg shadow-lg shadow-primary/30 w-full md:w-auto px-12 group hover:scale-105 transition-transform"
            :disabled="isSearching"
          >
            <span v-if="!isSearching" class="flex items-center gap-2">
              <Search class="w-5 h-5 group-hover:rotate-12 transition-transform" /> 
              Find My Top 5 Matches
            </span>
            <span v-else class="flex items-center gap-2">
              <Loader2 class="w-5 h-5 animate-spin" />
              Algorithm Analyzing Queue...
            </span>
          </button>
        </div>

      </div>
    </div>

    <!-- Success Toast Notification -->
    <div v-if="showSuccessMsg" class="toast toast-top toast-center z-50">
      <div class="alert alert-success shadow-lg text-white">
        <CheckCircle2 class="w-5 h-5"/>
        <span>Freelancer Dispatched! Notification sent.</span>
      </div>
    </div>

    <!-- RESULTS SECTION -->
    <div class="mt-16" v-if="isSearching || matchComplete">
        <h3 class="text-2xl font-bold mb-6 text-center">Your Curated Matches</h3>
        
        <div v-if="isSearching" class="flex flex-col items-center justify-center p-12 space-y-4">
           <span class="loading loading-bars loading-lg text-primary"></span>
           <p class="animate-pulse text-base-content/60">Scanning available pool & ensuring fair rotation...</p>
        </div>
        
        <div v-else-if="matchComplete && matchedCandidates.length === 0" class="text-center p-12 bg-base-200 rounded-box border border-base-300 border-dashed">
            <div class="text-4xl mb-3">🕵️‍♂️</div>
            <h4 class="text-xl font-bold">No available freelancers found</h4>
            <p class="text-base-content/70">Try reducing required skills or wait for active freelancers to finish.</p>
        </div>

        <div v-else>
            <TransitionGroup name="list" tag="div" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div v-for="(candidate, index) in matchedCandidates" :key="candidate.id" 
                   class="card bg-base-100 shadow-xl border border-base-200 hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group">
                
                <div class="card-body p-6">
                  <!-- Match Badge -->
                  <div class="absolute -top-3 -right-3 badge badge-primary gap-1 shadow-md font-bold p-3">
                    Queue Pick
                  </div>
                  
                  <div class="flex items-start gap-4 mb-4">
                    <div class="avatar">
                      <div class="w-16 rounded-full ring ring-primary ring-offset-base-100 ring-offset-2">
                        <img :src="`https://api.dicebear.com/7.x/notionists/svg?seed=${candidate.name.replace(' ','')}`" alt="avatar" />
                      </div>
                    </div>
                    <div>
                      <h2 class="card-title text-xl">{{ candidate.name }}</h2>
                      <div class="flex items-center gap-1 text-sm font-semibold text-warning mt-1 mb-1">
                        <Star class="w-4 h-4 fill-current"/> {{ candidate.rating.toFixed(1) }}
                      </div>
                      <div v-if="candidate.status === 'invited'" class="badge badge-ghost badge-sm gap-1 text-base-content/70">
                        <Loader2 class="w-3 h-3 animate-spin"/> Waiting for response...
                      </div>
                    </div>
                  </div>
                  
                  <div class="flex flex-wrap gap-1 mb-6">
                    <span v-for="skill in candidate.skills" :key="skill" class="badge badge-sm badge-neutral">{{ skill }}</span>
                  </div>

                  <div class="card-actions flex-col mt-auto gap-2">
                    <button v-if="candidate.status !== 'invited'" 
                            @click="sendInvite(candidate)" 
                            :disabled="candidate.isInviting"
                            class="btn btn-primary btn-block group-hover:btn-active">
                      <span v-if="candidate.isInviting"><Loader2 class="w-4 h-4 animate-spin"/> Sending...</span>
                      <span v-else>Send Job Invite <Mail class="w-4 h-4 ml-1"/></span>
                    </button>

                    <template v-else>
                      <button @click="declineFreelancer(candidate.id)" class="btn btn-outline btn-error btn-sm btn-block">
                        Simulate Decline (Auto-replace)
                      </button>
                    </template>
                  </div>
                </div>
              </div>
            </TransitionGroup>
        </div>
    </div>
  </div>
</template>

<style scoped>
.list-enter-active,
.list-leave-active {
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.list-enter-from {
  opacity: 0;
  transform: translateY(30px) scale(0.9);
}
.list-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
</style>
