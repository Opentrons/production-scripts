<template>
    <div class="host_selector">
        <el-form :inline="true"  class="demo-form-inline">
            <el-form-item label="UserName">
            <el-input  placeholder="root" />
            </el-form-item>
            <el-form-item label="HostName">
            <el-select  placeholder="Activity zone">
                <el-option label="Zone one" value="shanghai" />
                <el-option label="Zone two" value="beijing" />
            </el-select>
            </el-form-item>
            <el-form-item>
            <el-button type="primary" @click="onSubmit">Save</el-button>
            </el-form-item>
        </el-form>
        
    </div>
  </template>
  
  <script>


  export default {
    name: 'HostInfo',
    props: {
      msg: String,
      page_id: String
    },

    data(){
        return{
           

        }
    },
    methods: {
        onSubmit() {
            console.log('submit!')
        }
    }
  }




import { reactive } from 'vue'

const formInline = reactive({
  user: '',
  region: '',
})

const onSubmit = () => {
  console.log('submit!')
}






  </script>
  
  <!-- Add "scoped" attribute to limit CSS to this component only -->
  <style scoped lang="scss">
    .host_selector {
        padding-left: 40px;
    }
  </style>