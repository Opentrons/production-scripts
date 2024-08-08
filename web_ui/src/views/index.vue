<template>
<el-config-provider :locale="locale">
    <div class="index-box">
        <div class="left-box">
            <img alt="logo-img" src="../assets/logo2.png" class="logo-main">
            <el-menu active-text-color="#ffd04b" class="el-menu-left" background-color="#16212d" text-color="#fff"
                :router="true" :default-active="active_uri">
                <el-sub-menu index="1">
                    <template #title>
                        <el-icon>
                            <Menu />
                        </el-icon>
                        <span>账号管理</span>
                    </template>

                    <el-menu-item index="1-1">角色管理</el-menu-item>
                    <el-menu-item index="1-2">用户管理</el-menu-item>

                </el-sub-menu>
                <el-sub-menu index="2">

                    <template #title>
                        <el-icon>
                            <UploadFilled />
                        </el-icon>
                        <span>数据处理</span>
                    </template>

                    <el-menu-item index="file_handler">上传下载</el-menu-item>
                    <el-menu-item index="2-2">数据分析</el-menu-item>
                    <el-menu-item index="2-23">数据统计</el-menu-item>


                </el-sub-menu>
                <el-sub-menu index="3">

                    <template #title>
                        <el-icon>
                            <Box />
                        </el-icon>
                        <span>设备管理</span>
                    </template>

                    <el-menu-item index="/device/status">设备状态</el-menu-item>
                    <el-menu-item index="/device/control">设备控制</el-menu-item>



                </el-sub-menu>
                <el-sub-menu index="4">

                <template #title>
                    <el-icon>
                        <Operation />
                    </el-icon>
                    <span>测试管理</span>
                </template>

                <el-menu-item index="/test_managment/status">测试状态</el-menu-item>
                <el-sub-menu index="4-2">
                    <template #title>开始测试</template>
                    <el-menu-item index="/test_managment/test/ot3">OT3</el-menu-item>
                    <el-menu-item index="/test_managment/test/pipette">Pipette 1/8CH</el-menu-item>
                    <el-menu-item index="/test_managment/test/pipette/96ch">Pipette 96CH</el-menu-item>
                </el-sub-menu>



</el-sub-menu>
                <el-menu-item index="/document">
                    <el-icon>
                        <FolderOpened />
                    </el-icon>
                    <span>测试文档</span>
                </el-menu-item>
                <el-menu-item index="4">
                    <el-icon>
                        <Setting />
                    </el-icon>
                    <span>设置</span>
                </el-menu-item>

            </el-menu>

        </div>
        <div class="right-box">
            <div class="top-box">
                <el-menu class="el-menu-top" mode="horizontal" :ellipsis="false" :default-active="active_uri"
                    :router="true" background-color="#16212d" text-color="#fff" active-text-color="#ffd04b">
                    <el-menu-item index="/home">
                        <el-icon>
                            <HomeFilled />
                        </el-icon>
                        首页
                    </el-menu-item>
                    <el-menu-item index="/test_manage">
                        <el-icon>
                            <Histogram />
                        </el-icon>
                        数据
                    </el-menu-item>
                    <el-sub-menu index="2">
                     
                        <template #title> <el-icon><Reading /></el-icon>{{_lan}}</template>
                        <el-menu-item @click="toEnglist">English</el-menu-item>
                        <el-menu-item @click="toChinese">中文</el-menu-item>
                    </el-sub-menu>

                    <el-sub-menu index="3">
                       
                        <template #title> <el-icon><user-filled /></el-icon>登录用户</template>
                        <el-menu-item index="3-1">个人中心</el-menu-item>
                        <el-menu-item index="3-2">修改密码</el-menu-item>
                        <el-menu-item index="3-3">退出登录</el-menu-item>
                    </el-sub-menu>

                </el-menu>

            </div>
            <div class="content-box">
                <router-view></router-view>
            </div>
        </div>
    </div>
</el-config-provider>
</template>

<script setup lang="ts">

import {
    UserFilled, UploadFilled, FolderOpened, Setting, HomeFilled, Operation, Menu, Box, Histogram, Microphone, Reading
} from '@element-plus/icons-vue';

import { ref, Ref, computed } from "vue";
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import en from 'element-plus/dist/locale/en.mjs'

let active_uri: Ref<string> = ref("/home")

const _lan = ref("语言")
const language = ref('zh-cn')
const locale = computed(() => (language.value === 'zh-cn' ? zhCn : en));

const toEnglist = () => {
    language.value = 'en'
    _lan.value = "Language"
}

const toChinese = () => {
    language.value = 'zh-cn'
    _lan.value = "语言"
}

</script>

<style scoped lang="scss">
.index-box {
    width: 100vw;
    height: 100vh;
    display: flex;

    .left-box {
        width: 200px;
        background-color: rgb(22, 33, 45);
        color: white;
        font-size: 10px;
        text-align: center;

        .logo-main {
            width: 180px;
            margin-top: 25px;
        }

        .el-menu {
            border-right: none
        }

        .el-menu-left {
            margin-top: 20px;
        }


    }

    .right-box {
        flex: 1;
        display: flex;
        flex-direction: column;

        .top-box {
            height: 60px;
            background-color: rgb(22, 33, 45);
            display: flex;
            justify-content: flex-end;
            padding-right: 10px;

            .el-menu {
                border-bottom: none;
            }
        }

        .content-box {
            flex: 1;
            padding: 10px;
            overflow: hidden;

        }
    }
}
</style>