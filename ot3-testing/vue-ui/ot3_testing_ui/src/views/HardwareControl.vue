<template>
  <div class="hostinfo">
    <HostInfo msg="m" page_id="0"/>
    <Jog msg="m" page_id="0"/>
  </div>
</template>

<script>
// @ is an alias to /src
import HostInfo from '@/components/HostInfo.vue'
import Jog from '@/components/HardwareControl/Jog.vue'

export default {
  name: 'HardwareControl',
  components: {
    HostInfo,
    Jog
  }
}
</script>

<style scoped>

</style>