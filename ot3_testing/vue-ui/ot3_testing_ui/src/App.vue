<template>
  <nav> 
    <el-menu
    router
    :default-active="$route.path"
    class="el-menu-root"
    mode="horizontal"
    :ellipsis="false"
  >
    <el-menu-item index="0"><img alt="Vue logo" src="./assets/logo.png" class="img_log"></el-menu-item>
    <div class="flex-grow" />
    <el-menu-item index="/">Home</el-menu-item>
    <el-menu-item index="/testflow">TestFlow</el-menu-item>
    <el-menu-item index="/hardware-control">HardwareControl</el-menu-item>
    <el-sub-menu index="4">
      <template #title>TestData</template>
      <el-menu-item index="4-1">Pull-Data</el-menu-item>
      <el-menu-item index="4-2">Analyze</el-menu-item>
      <el-menu-item index="4-3">Link-GoogleDrive</el-menu-item>
    </el-sub-menu>
    <el-menu-item index="/document">Document</el-menu-item>
    <el-menu-item index="/about">About</el-menu-item>
  </el-menu>
  </nav>
  <router-view/>
</template>

<script>
  

</script>


<style lang="scss">
  #app {
    font-family: Avenir, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-align: left;
    color: #2c3e50;
  }

  nav {
    padding: 30px;

    a {
      font-weight: bold;
      text-decoration:none;
      color: #000;
      // &.router-link-exact-active {
      //   color: #42b983;
      // }
    }
  }

  p {
    text-align: left;
    color: #2c3e50;

  }


  .flex-grow {
    flex-grow: 1;
  }

  .img_log {
    width: 150px;
  }
</style>
