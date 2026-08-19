import { useState } from "react";
import sx from "../sx.js";
import { MediaPickerDialog } from "./MediaPicker.jsx";
import { Button } from "./ui.jsx";

const previewFor = (file) => (typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "");

function PendingImage({ image, label, onRemove }) {
  return (
    <div style={sx`width:132px;display:flex;flex-direction:column;gap:7px;padding:8px;border:1px solid #E7DCF2;border-radius:12px;background:#fff`}>
      <span style={sx`width:116px;height:116px;border-radius:9px;background:#F5EDE3 url("${image.preview || image.url}") center/cover no-repeat`} />
      <span style={sx`font-size:11.5px;color:#766669;overflow:hidden;text-overflow:ellipsis;white-space:nowrap`}>{label}</span>
      <Button variant="danger" onClick={onRemove} style={sx`min-height:32px;padding:0;font-size:12px`}>إزالة</Button>
    </div>
  );
}

/** Stages device uploads and library URLs so the product form owns the whole image workflow. */
export default function ProductImagesEditor({ mainImage, queuedMain, queuedAdditional, onMainChange, onAdditionalAdd, onAdditionalRemove }) {
  const [pickerTarget, setPickerTarget] = useState(null);
  const makeFileImage = (file) => ({ file, preview: previewFor(file), label: file.name });
  const select = (url) => {
    const image = { url, preview: url, label: url };
    if (pickerTarget === "main") onMainChange(image);
    else onAdditionalAdd(image);
    setPickerTarget(null);
  };

  return (
    <div style={sx`display:flex;flex-direction:column;gap:16px`}>
      <div style={sx`display:flex;flex-direction:column;gap:9px`}>
        <strong>اختيار الغلاف (الصورة الرئيسية)</strong>
        <span style={sx`font-size:12.5px;color:#8A7F95`}>أول صورة بالترتيب هي غلاف المنتج.</span>
        {queuedMain ? (
          <PendingImage image={queuedMain} label="صورة رئيسية جديدة" onRemove={() => onMainChange(null)} />
        ) : mainImage ? (
          <div style={sx`display:flex;gap:10px;align-items:center`}>
            <span style={sx`width:92px;height:92px;border-radius:10px;background:#F5EDE3 url("${mainImage.url}") center/cover no-repeat`} />
            <span style={sx`font-size:13px;color:#766669`}>الصورة الرئيسية الحالية</span>
          </div>
        ) : <span style={sx`font-size:13px;color:#8A7F95`}>أضف صورة رئيسية ليظهر المنتج بصورة غلاف.</span>}
        <div style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
          <Button variant="secondary" onClick={() => setPickerTarget("main")}>اختيار من مكتبة الوسائط</Button>
          <label style={sx`display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border:1px solid #DCCDBC;border-radius:9px;cursor:pointer;font-size:13px;font-weight:700`}>
            رفع من الجهاز
            <input aria-label="الصورة الرئيسية — رفع من الجهاز" type="file" accept="image/*" hidden onChange={(event) => {
              const [file] = event.target.files;
              if (file) onMainChange(makeFileImage(file));
              event.target.value = "";
            }} />
          </label>
        </div>
      </div>

      <div style={sx`display:flex;flex-direction:column;gap:9px`}>
        <strong>صور إضافية</strong>
        <span style={sx`font-size:12.5px;color:#8A7F95`}>اختيارية — يمكن ترتيب الصور المحفوظة بالسحب أو الأسهم.</span>
        <div style={sx`display:flex;gap:10px;flex-wrap:wrap`}>
          {queuedAdditional.map((image, index) => <PendingImage key={`${image.url || image.label}-${index}`} image={image} label={image.label || "صورة جديدة"} onRemove={() => onAdditionalRemove(index)} />)}
        </div>
        <div style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
          <Button variant="secondary" onClick={() => setPickerTarget("additional")}>اختيار من مكتبة الوسائط</Button>
          <label style={sx`display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border:1px solid #DCCDBC;border-radius:9px;cursor:pointer;font-size:13px;font-weight:700`}>
            رفع من الجهاز
            <input aria-label="صور إضافية — رفع من الجهاز" type="file" accept="image/*" multiple hidden onChange={(event) => {
              [...event.target.files].forEach((file) => onAdditionalAdd(makeFileImage(file)));
              event.target.value = "";
            }} />
          </label>
        </div>
      </div>

      {pickerTarget && <MediaPickerDialog onClose={() => setPickerTarget(null)} onSelect={select} />}
    </div>
  );
}
