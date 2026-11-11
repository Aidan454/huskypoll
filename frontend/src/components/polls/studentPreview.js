// Whitelist only fields displayed to students. Never copy answer keys or explanations.
export function studentPreviewQuestion(form, pictureUrl) {
  return {
    type: form.type,
    body_md: form.body_md.trim(),
    body_media_url: pictureUrl || null,
    options: form.type.startsWith('mc')
      ? form.options.filter((option) => option.text_md.trim()).map((option, index) => ({
          id: index + 1,
          letter: String.fromCharCode(65 + index),
          text_md: option.text_md.trim(),
        }))
      : [],
  }
}
