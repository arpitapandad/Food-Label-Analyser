/**
 * Phone-camera photos need shrinking before they are uploaded.
 *
 * A modern phone writes 8-12 MP JPEGs (3-8 MB each). Sending two of those
 * together regularly exceeds the server's per-request limit and makes OCR slow
 * enough to feel broken. The browser can do better: decode the photo (applying
 * its EXIF rotation), draw it to a canvas at a sane size, and re-encode it as a
 * compact JPEG. Label text stays legible at 2000 px, while the upload drops to
 * a few hundred kilobytes.
 */

const MAX_EDGE = 2000
const JPEG_QUALITY = 0.85
/** Small images that are already compact are left untouched. */
const KEEP_UNDER_BYTES = 600 * 1024

/**
 * Return a File suitable for uploading. Never throws: if the browser cannot
 * decode or re-encode the image, the original file is returned unchanged.
 */
export async function prepareImageForUpload(file) {
  if (!file || !String(file.type || '').startsWith('image/')) return file
  // Do not flatten an animated GIF someone may have picked by mistake.
  if (file.type === 'image/gif') return file

  let decoded = null
  try {
    decoded = await decode(file)
    if (!decoded) return file

    const { source, width, height } = decoded
    if (!width || !height) return file

    const scale = Math.min(1, MAX_EDGE / Math.max(width, height))
    if (scale === 1 && file.size <= KEEP_UNDER_BYTES) return file

    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))

    const ctx = canvas.getContext('2d')
    if (!ctx) return file

    // Transparent PNGs would turn black in a JPEG; labels are on white stock.
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(source, 0, 0, canvas.width, canvas.height)

    const blob = await toBlob(canvas)
    if (!blob) return file
    // Re-encoding a small, already efficient image can make it bigger.
    if (blob.size >= file.size && scale === 1) return file

    return new File([blob], jpegName(file.name), {
      type: 'image/jpeg',
      lastModified: Date.now(),
    })
  } catch {
    return file
  } finally {
    decoded?.close?.()
  }
}

/** Decode with EXIF orientation applied, with an <img> fallback for old Safari. */
async function decode(file) {
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return { source: bitmap, width: bitmap.width, height: bitmap.height, close: () => bitmap.close() }
    } catch {
      // Fall through to the <img> path.
    }
  }

  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      resolve({
        source: img,
        width: img.naturalWidth,
        height: img.naturalHeight,
        close: () => URL.revokeObjectURL(url),
      })
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(null)
    }
    img.src = url
  })
}

function toBlob(canvas) {
  return new Promise((resolve) => {
    try {
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', JPEG_QUALITY)
    } catch {
      resolve(null)
    }
  })
}

function jpegName(name) {
  const stem = String(name || 'label').replace(/\.[^.]+$/, '') || 'label'
  return `${stem}.jpg`
}
