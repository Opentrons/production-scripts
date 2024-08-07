<template>
    <div class="document-main-box">
        <div class="document-head-box">
            <el-button type="primary" @click="newDocument"> 新建文档 </el-button>
        </div>
        <div class="document-content-box">
            <el-drawer v-model="drawer" title="编辑文档" direction="rtl" :before-close="handleClose">
                <MyEditor />
                <el-button type="primary" style="margin-top: 10px; text-align: right;"> 提交 </el-button>
            </el-drawer>
            
            <el-table :data="filterTableData" style="width: 100%">
                <el-table-column label="发布日期" prop="date" />
                <el-table-column label="作者" prop="name" />
                <el-table-column label="标题" prop="title" />
                <el-table-column label="标签" prop="tag" />
                <el-table-column align="right">
                <template #header>
                    <el-input v-model="search" size="small" placeholder="根据作者名字搜索" />
                </template>
                <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.$index, scope.row)"
                    >编辑</el-button
                    >
                    <el-button size="small" type="info" @click=""
                    >详情</el-button
                    >
                    <el-button
                    size="small"
                    type="danger"
                    @click="handleDelete(scope.$index, scope.row)"
                    >删除</el-button
                    >
                </template>
                </el-table-column>
            </el-table>
           


        </div>

    </div>






</template>

<script lang="ts" setup>
import MyEditor from '../../components/MyEditor.vue';
import { ref, computed} from 'vue';
import { ElMessageBox } from 'element-plus'
import { tr } from 'element-plus/es/locales.mjs';

let drawer = ref(false)

const handleClose = (done: () => void) => {
    ElMessageBox.confirm('Are you sure you want to close this?')
        .then(() => {
            done()
        })
        .catch(() => {
            // catch error
        })
};

const newDocument = () => {
    drawer.value = true
}

// document

interface User {
  date: string
  name: string
  title: string
  address: string
  tag: string
}

const search = ref('')
const filterTableData = computed(() =>
  tableData.filter(
    (data) =>
      !search.value ||
      data.name.toLowerCase().includes(search.value.toLowerCase())
  )
)
const handleEdit = (index: number, row: User) => {
  console.log(index, row)
}
const handleDelete = (index: number, row: User) => {
  console.log(index, row)
}

const tableData: User[] = [
  {
    date: '2016-05-03',
    name: 'Tom',
    title: "how to slove the terrible things",
    address: 'No. 189, Grove St, Los Angeles',
    tag: "SOP",
  },
  {
    date: '2016-05-02',
    name: 'John',
    title: "how to slove the terrible things",
    address: 'No. 189, Grove St, Los Angeles',
    tag: "SOP",
  },
  {
    date: '2016-05-04',
    name: 'Morgan',
    title: "how to slove the terrible things",
    address: 'No. 189, Grove St, Los Angeles',
    tag: "SOP",
  },
  {
    date: '2016-05-01',
    name: 'Jessy',
    title: "how to slove the terrible things",
    address: 'No. 189, Grove St, Los Angeles',
    tag: "SOP",
  },
]

</script>

<style lang="scss" scoped>
.document-main-box {
    display: flex;
    height: 100vh -100px;
    width: 100vw -200px;
    flex-direction: column;

    .document-head-box {
        height: 50px;
    }

    .document-content-box {

        height: 1000px;

    }
}
</style>