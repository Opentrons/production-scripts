<template>
  <div style="border: 1px solid #ccc">
    <Toolbar
      style="border-bottom: 1px solid #ccc"
      :editor="editorRef"
      :defaultConfig="toolbarConfig"
      :mode="mode"
    />
    <Editor
      style="height: 500px; overflow-y: hidden;"
      v-model="valueHtml"
      :defaultConfig="editorConfig"
      :mode="mode"
      @onCreated="handleCreated"
    />
  </div>
</template>

<script>
import '@wangeditor/editor/dist/css/style.css'
import { onBeforeUnmount, ref, shallowRef } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'

export default {
  components: { Editor, Toolbar },
  props: {
    modelValue: {
      type: String,
      default: ''
    }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const editorRef = shallowRef()
    const valueHtml = ref(props.modelValue || '<p>请输入内容...</p>')

    const toolbarConfig = {}
    const editorConfig = { 
      placeholder: '请输入内容...',
      MENU_CONF: {
        uploadImage: {
          server: '/api/upload', // 你的图片上传接口
          fieldName: 'file'
        }
      }
    }

    const handleCreated = (editor) => {
      editorRef.value = editor
      editor.on('change', () => {
        const html = editor.getHtml()
        emit('update:modelValue', html)
      })
    }

    onBeforeUnmount(() => {
      const editor = editorRef.value
      if (editor == null) return
      editor.destroy()
    })

    return {
      editorRef,
      valueHtml,
      mode: 'default',
      toolbarConfig,
      editorConfig,
      handleCreated
    }
  }
}
</script>