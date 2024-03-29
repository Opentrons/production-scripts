<template>
  <div class="home">
    <Welcome msg="Welcome to home page" page_id="0"/>
    <img alt="Vue logo" src="../assets/home_OT2.png">
  </div>
</template>

<script>
// @ is an alias to /src
import Welcome from '@/components/Welcome.vue'

export default {
  name: 'HomeView',
  components: {
    Welcome
  }
}
</script>

<style scoped>
  .home{
    text-align: center;
  }
</style>
