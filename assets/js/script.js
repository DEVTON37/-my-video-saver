// Floating Icons Background Logic
function initFloatingIcons() {
    const container = document.getElementById('floating-icons');
    if (!container) return;

    const icons = [
        'fa-video', 'fa-play', 'fa-film', 'fa-camera', 'fa-youtube', 
        'fa-facebook', 'fa-tiktok', 'fa-instagram', 'fa-tv', 'fa-clapperboard'
    ];

    const iconCount = 20;

    for (let i = 0; i < iconCount; i++) {
        const iconEl = document.createElement('i');
        const randomIcon = icons[Math.floor(Math.random() * icons.length)];
        
        iconEl.className = `fas ${randomIcon} floating-icon`;
        
        // Random positioning and timing
        const left = Math.random() * 100;
        const duration = 15 + Math.random() * 25;
        const delay = Math.random() * -30; // Negative delay to start mid-animation
        const drift = (Math.random() - 0.5) * 200; // Drift left or right
        const size = 1 + Math.random() * 2; // Random size

        iconEl.style.left = `${left}%`;
        iconEl.style.setProperty('--duration', `${duration}s`);
        iconEl.style.setProperty('--drift', `${drift}px`);
        iconEl.style.animationDelay = `${delay}s`;
        iconEl.style.fontSize = `${size}rem`;

        container.appendChild(iconEl);
    }
}

// Initialize on load
window.addEventListener('DOMContentLoaded', initFloatingIcons);

const videoUrlInput = document.getElementById('video-url');
const platformIcon = document.getElementById('platform-icon');

videoUrlInput.addEventListener('input', function() {
    const url = this.value.toLowerCase();
    platformIcon.className = 'text-xl transition-all duration-300 ';
    
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
        platformIcon.className += 'fab fa-youtube text-red-500';
    } else if (url.includes('facebook.com') || url.includes('fb.watch')) {
        platformIcon.className += 'fab fa-facebook text-blue-600';
    } else if (url.includes('tiktok.com')) {
        platformIcon.className += 'fab fa-tiktok text-pink-500';
    } else if (url.includes('instagram.com')) {
        platformIcon.className += 'fab fa-instagram text-purple-500';
    } else if (url.includes('twitter.com') || url.includes('x.com')) {
        platformIcon.className += 'fab fa-twitter text-blue-400';
    } else if (url.includes('dailymotion.com') || url.includes('dai.ly')) {
        platformIcon.className += 'fas fa-play-circle text-blue-500';
    } else if (url.includes('vimeo.com')) {
        platformIcon.className += 'fas fa-video text-green-500';
    } else if (url.includes('bilibili.com') || url.includes('bilibili.tv')) {
        platformIcon.className += 'fas fa-tv text-pink-400';
    } else {
        platformIcon.className += 'fas fa-link text-blue-500';
    }
});

document.getElementById('download-trigger').addEventListener('click', async function() {
    const url = document.getElementById('video-url').value;
    const quality = document.getElementById('video-quality').value;
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressStatus = document.getElementById('progress-status');
    const downloadBtn = document.getElementById('download-trigger');

    if (!url) {
        alert('กรุณาวางลิงก์วิดีโอก่อนนะคะคุณพี่ ❤️');
        return;
    }

    // Show progress
    progressContainer.classList.remove('hidden');
    progressStatus.classList.remove('text-green-500', 'font-bold'); // Reset colors
    document.getElementById('success-actions').classList.add('hidden'); // Hide old actions
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> กำลังดาวน์โหลดจริง...';
    
    // Simulate initial progress while waiting for server
    progressBar.style.width = '10%';
    progressPercent.innerText = '10%';
    progressStatus.innerText = 'นุ่นกำลังส่งคำขอไปยังเซิร์ฟเวอร์นะคะ...';

    try {
        const response = await fetch('/api/download', { // Use relative path to avoid CORS issues if port changes
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                url: url,
                quality: quality
            })
        });

        // First check if response is OK
        if (!response.ok) {
            let result;
            try {
                const text = await response.text();
                try {
                    result = JSON.parse(text);
                } catch (e) {
                    console.error('Failed to parse error JSON:', text);
                }
            } catch (e) {
                console.error('Failed to read response body:', e);
            }

            // Use the specific error from server if available
            if (result && result.error) {
                throw new Error(result.error);
            }
            
            let errorMessage = `เซิร์ฟเวอร์ขัดข้อง (รหัส: ${response.status})`;
            
            if (response.status === 501) {
                errorMessage = "นุ่นตรวจพบว่าระบบขาดโปรแกรม FFmpeg ค่ะ นุ่นเลยปรับมาใช้ 'โหมดความเข้ากันได้' แทน ลองกดอีกครั้งนะคะ! (Error 501)";
            } else if (response.status === 500) {
                // Determine if it's YouTube or another site to make error message more accurate
                const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
                if (isYouTube) {
                    errorMessage = "อุ๊ย! YouTube ปฏิเสธการดาวน์โหลดค่ะ ลองเปลี่ยนความละเอียดเป็น 360p หรือ 480p ดูนะคะ (Error 500)";
                } else {
                    errorMessage = "อุ๊ย! เว็บไซต์นี้ปฏิเสธการดาวน์โหลดชั่วคราวค่ะ นุ่นพยายามลองหลายวิธีแล้วแต่ยังไม่ได้ ลองเปลี่ยนความละเอียดหรือตรวจสอบลิงก์อีกครั้งนะคะ (Error 500)";
                }
            }
            
            console.error('Server Error:', errorMessage);
            throw new Error(errorMessage);
        }

        let result;
        try {
            result = await response.json();
        } catch (e) {
            const text = await response.text();
            console.error('Invalid JSON response:', text);
            throw new Error('เซิร์ฟเวอร์ส่งข้อมูลกลับมาผิดพลาด (ไม่ใช่ JSON)');
        }

        if (result.success) {
            progressBar.style.width = '100%';
            progressPercent.innerText = '100%';
            // Update progress status with success message (replacing alert)
            const successMsg = result.message || `ดาวน์โหลด "${result.title || result.file}" เรียบร้อยแล้วค่ะ! ✨`;
            progressStatus.innerText = successMsg;
            progressStatus.classList.add('text-green-500', 'font-bold'); // Make it stand out
            
            downloadBtn.innerHTML = '<i class="fas fa-check"></i> ดาวน์โหลดเรียบร้อยค่ะ';
            
            // Show action buttons
            const successActions = document.getElementById('success-actions');
            const openFolderBtn = document.getElementById('open-folder-btn');
            const browserDownloadLink = document.getElementById('browser-download-link');
            
            successActions.classList.remove('hidden');
            browserDownloadLink.href = `/api/get-file/${encodeURIComponent(result.file)}`;
            browserDownloadLink.download = result.file;
            
            openFolderBtn.onclick = async () => {
                try {
                    await fetch('/api/open-folder', { method: 'POST' });
                } catch (e) {
                    alert('ไม่สามารถเปิดโฟลเดอร์ได้โดยอัตโนมัติค่ะ แต่ไฟล์อยู่ที่: c:\\Users\\adsdwdd\\TON\\video-downloader-web\\downloads');
                }
            };
            
            setTimeout(() => {
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '<i class="fas fa-download"></i> เริ่มดาวน์โหลดเลยค่ะ';
                // We keep the actions visible until the next download starts
            }, 5000);
        } else {
            throw new Error(result.error || 'เกิดข้อผิดพลาดบางอย่างค่ะ');
        }
    } catch (error) {
        console.error('Error:', error);
        progressStatus.innerText = 'ขอโทษนะคะ เกิดข้อผิดพลาด: ' + error.message;
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ลองใหม่อีกครั้งค่ะ';
        alert('อุ๊ย! ' + error.message);
    }
});
