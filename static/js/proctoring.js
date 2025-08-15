document.addEventListener('DOMContentLoaded', async function() {
    // Initialize variables for AI proctoring
    let model;
    let video;
    let canvas;
    let faceDetectionInterval;
    let suspiciousActivityCount = 0;
    let phoneDetectionCount = 0;
    let multipleFacesDetectionCount = 0;
    let tabSwitchCount = 0;
    let lastTabSwitchTime = null;
    const sessionId = document.getElementById('session-id')?.value || {{ session_id }}; // Fallback if element not found
    
    // Set up webcam and start monitoring
    async function setupProctoring() {
        try {
            console.log('Setting up AI proctoring...');
            
            // Get user media with constraints for better quality
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'user',
                    frameRate: { min: 15, ideal: 30 }
                },
                audio: false
            });
            
            // Set up video element
            video = document.getElementById('webcam-video');
            if (!video) {
                console.error("Webcam video element not found");
                logProctoringEvent('setup_failure', 'Webcam video element not found in DOM');
                return;
            }
            
            video.srcObject = stream;
            
            // Wait for video to load
            await new Promise(resolve => {
                video.onloadedmetadata = () => {
                    video.play(); // Ensure video is playing
                    resolve();
                };
            });
            
            // Set up canvas for processing
            canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Log successful webcam setup
            logProctoringEvent('webcam_setup', 'Webcam accessed successfully');
            
            // Load AI model - we'll use a simpler face detection approach if blazeface isn't available
            if (typeof blazeface !== 'undefined') {
                console.log('Loading Blazeface model...');
                model = await blazeface.load();
                console.log('Blazeface model loaded successfully');
                // Start monitoring
                startFaceDetection();
                logProctoringEvent('ai_setup', 'Face detection AI model loaded successfully');
            } else {
                console.warn("Blazeface library not found. Using fallback detection method.");
                logProctoringEvent('setup_warning', 'Using fallback face detection method');
                startFallbackDetection();
            }
            
            // Display webcam feed
            document.getElementById('video-container').style.display = 'block';
            
            console.log('Proctoring setup complete');
            logProctoringEvent('setup_success', 'Proctoring setup completed successfully');
            
        } catch (error) {
            console.error('Error setting up proctoring:', error);
            showWarning('Failed to access webcam. Please enable webcam access to continue the exam.');
            logProctoringEvent('setup_failure', 'Failed to set up webcam: ' + error.message);
        }
    }
    
    // Start face detection monitoring - FIXED
    function startFaceDetection() {
        console.log('Starting face detection monitoring...');
        faceDetectionInterval = setInterval(async () => {
            try {
                if (!model || !video || !canvas) {
                    console.error("Model, video, or canvas not initialized");
                    return;
                }
                
                // Make sure video is still playing and not frozen
                if (video.paused || video.ended) {
                    console.warn("Video is not playing. Attempting to restart...");
                    await video.play().catch(err => {
                        logProctoringEvent('video_error', 'Failed to restart video: ' + err.message);
                    });
                }
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                // Get image data for processing
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                
                // Run face detection - more robust by adding try/catch
                let predictions = [];
                try {
                    predictions = await model.estimateFaces(video, false); // Set to false for better performance
                    console.log(`Face detection result: ${predictions.length} faces detected`);
                } catch (detectionErr) {
                    console.error('Error during face estimation:', detectionErr);
                    logProctoringEvent('detection_algorithm_error', 'Face detection algorithm error: ' + detectionErr.message);
                    return; // Skip this detection cycle
                }
                
                // FIXED: Properly handle face detection scenarios
                
                // No face detected
                if (predictions.length === 0) {
                    suspiciousActivityCount++;
                    console.log(`No face detected (count: ${suspiciousActivityCount})`);
                    if (suspiciousActivityCount >= 2) { // Reduced from 3 to 2 for faster detection
                        showWarning('No face detected. Please ensure your face is visible to the camera.');
                        const screenshot = canvas.toDataURL('image/jpeg', 0.7); // Higher quality for better evidence
                        logProctoringEvent('face_missing', `No face detected in frame (${suspiciousActivityCount} consecutive frames)`, screenshot);
                        
                        // Reset after specific threshold to avoid continuous warnings
                        if (suspiciousActivityCount >= 5) {
                            suspiciousActivityCount = 2; // Keep it in warning state but don't continuously log
                        }
                    }
                }
                // Multiple faces detected - IMPROVED
                else if (predictions.length > 1) {
                    multipleFacesDetectionCount++;
                    console.log(`Multiple faces detected: ${predictions.length} (count: ${multipleFacesDetectionCount})`);
                    
                    // Always show warning when multiple faces are detected
                    showWarning(`Multiple faces detected (${predictions.length}). Only the test taker should be present.`);
                    
                    // Take screenshot for evidence - improved quality
                    const screenshot = canvas.toDataURL('image/jpeg', 0.8);
                    
                    // Strengthen the multiple faces detection logging and alert
                    logProctoringEvent('multiple_faces', 
                        `${predictions.length} faces detected in frame (${multipleFacesDetectionCount} total detections). This is a violation of exam integrity.`, 
                        screenshot);
                    
                    // Additional violation log at higher counts
                    if (multipleFacesDetectionCount >= 3) {
                        logProctoringEvent('serious_violation', 
                            `Persistent multiple persons detected during exam (${multipleFacesDetectionCount} occurrences so far)`, 
                            screenshot);
                    }
                    
                    // Reset count after logging to prevent overflow but keep detection active
                    if (multipleFacesDetectionCount > 10) {
                        multipleFacesDetectionCount = 5;
                    }
                }
                // Single face - check for possible phone usage - IMPROVED DETECTION
                else if (predictions.length === 1) {
                    // Reset no-face counter since face is detected
                    suspiciousActivityCount = 0; 
                    
                    // Get the detected face
                    const face = predictions[0];
                    
                    // IMPROVED: Phone usage detection with lower thresholds and better sensitivity
                    
                    // 1. Calculate face position metrics
                    const faceCenterY = (face.topLeft[1] + face.bottomRight[1]) / 2;
                    const frameHeight = video.videoHeight;
                    const relativePosition = faceCenterY / frameHeight;
                    
                    // 2. Calculate head tilt if landmarks are available
                    let headTiltDown = false;
                    if (face.landmarks && face.landmarks.length >= 6) {
                        // Using eye and nose position to estimate head tilt
                        const leftEye = face.landmarks[0];
                        const rightEye = face.landmarks[1];
                        const nose = face.landmarks[2];
                        
                        // Calculate vertical relationship between eyes and nose
                        const eyeLevel = (leftEye[1] + rightEye[1]) / 2;
                        const noseToEyeVertical = nose[1] - eyeLevel;
                        
                        // Lower threshold for detecting tilt (more sensitive)
                        if (noseToEyeVertical > 8) { // Reduced from 10
                            headTiltDown = true;
                        }
                    }
                    
                    // IMPROVED PHONE DETECTION LOGIC - multiple factors with increased sensitivity
                    let lookingDown = false;
                    
                    // Criteria for looking down - more sensitive thresholds:
                    // 1. Face positioned lower in frame
                    if (relativePosition > 0.6) { // Reduced from 0.65
                        lookingDown = true;
                    }
                    
                    // 2. Head tilting down based on landmarks (if available)
                    if (headTiltDown) {
                        lookingDown = true;
                    }
                    
                    // 3. Face rotated down (if rotation data available)
                    if (face.probability < 0.9) { // Increased threshold from 0.85
                        lookingDown = true;
                    }
                    
                    // If looking down detected
                    if (lookingDown) {
                        phoneDetectionCount++;
                        console.log(`Possible phone usage detected (count: ${phoneDetectionCount})`);
                        
                        // Take action after consistent detections - more sensitive
                        if (phoneDetectionCount >= 2) { // Reduced threshold for faster detection
                            showWarning('You appear to be looking down. Please keep your eyes on the screen.');
                            
                            // Take screenshot for evidence
                            const screenshot = canvas.toDataURL('image/jpeg', 0.8);
                            
                            // IMPROVED: Phone usage logging
                            logProctoringEvent('phone_usage_suspected', 
                                `User appears to be looking down at phone (${phoneDetectionCount} consecutive frames)`, 
                                screenshot);
                            
                            if (phoneDetectionCount >= 4) {
                                logProctoringEvent('serious_violation', 
                                    'Consistent pattern of looking down indicates potential use of unauthorized device', 
                                    screenshot);
                                // Don't reset counter fully to maintain detection sensitivity
                                phoneDetectionCount = 2;
                            }
                        }
                    } else {
                        // Reset counter more slowly when properly facing screen
                        if (phoneDetectionCount > 0) {
                            phoneDetectionCount = Math.max(0, phoneDetectionCount - 0.5); // Slower decay
                        }
                    }
                }
                
                // Periodic random checks for audit trail
                if (Math.random() < 0.01) { // 1% chance per check
                    const screenshot = canvas.toDataURL('image/jpeg', 0.6); // Lower quality for routine checks
                    logProctoringEvent('random_check', 'Routine proctoring check', screenshot);
                }
                
            } catch (error) {
                console.error('Error in face detection cycle:', error);
                logProctoringEvent('detection_error', 'Error in face detection cycle: ' + error.message);
            }
        }, 1500); // Check more frequently - changed from 2000ms to 1500ms
    }
    
    // Fallback detection method if blazeface isn't available
    function startFallbackDetection() {
        console.log('Starting fallback detection...');
        faceDetectionInterval = setInterval(() => {
            try {
                if (!video || !canvas) {
                    console.error("Video or canvas not initialized");
                    return;
                }
                
                // Take screenshots for manual review
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                // Take periodic screenshots more frequently without AI
                if (Math.random() < 0.1) { // 10% chance - more frequent
                    const screenshot = canvas.toDataURL('image/jpeg', 0.6);
                    logProctoringEvent('fallback_monitoring', 'Periodic screenshot (no AI detection)', screenshot);
                }
            } catch (error) {
                console.error('Error in fallback detection:', error);
            }
        }, 3000); // Every 3 seconds
    }
    
    // FIXED: Log proctoring events to server with proper URL prefix and improved error handling
    async function logProctoringEvent(logType, details, screenshot = null) {
        try {
            console.log(`Logging proctoring event: ${logType} - ${details}`);
            
            const data = {
                session_id: sessionId,
                log_type: logType,
                details: details,
                timestamp: new Date().toISOString(),
                screenshot: screenshot,
                browser_info: getBrowserInfo(), // Additional data
                client_timestamp: new Date().getTime() // For time verification
            };
            
            // FIXED: Use the correct URL with proper prefix
            const response = await fetch('/student/api/proctoring/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify(data),
                // Add timeout to prevent hanging requests
                signal: AbortSignal.timeout(10000) // 10 second timeout
            });
            
            console.log(`Log response status: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }
            
            const result = await response.json();
            
            if (result.status !== 'success') {
                console.error('Failed to log proctoring event:', result.message);
                // Queue for retry
                retryLogEvent(data);
            }
            
            return result;
        } catch (error) {
            console.error('Failed to log proctoring event:', error);
            
            // Store failed logs in local cache and retry later
            retryLogEvent({
                session_id: sessionId,
                log_type: logType,
                details: details,
                timestamp: new Date().toISOString(),
                screenshot: screenshot ? (screenshot.length > 1000 ? 'data:image/jpeg;base64,/9j/4AAQ...(truncated)' : screenshot) : null
            });
        }
    }
    
    // Function to get browser information
    function getBrowserInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            screenWidth: window.screen.width,
            screenHeight: window.screen.height,
            devicePixelRatio: window.devicePixelRatio
        };
    }
    
    // Queue for retry mechanism - with local storage backup
    let eventRetryQueue = [];
    
    // Load any saved events from localStorage
    try {
        const savedQueue = localStorage.getItem('proctoring_retry_queue');
        if (savedQueue) {
            const parsedQueue = JSON.parse(savedQueue);
            if (Array.isArray(parsedQueue)) {
                eventRetryQueue = parsedQueue;
                console.log(`Loaded ${eventRetryQueue.length} saved events from local storage`);
            }
        }
    } catch (e) {
        console.error('Error loading saved events:', e);
    }
    
    function retryLogEvent(eventData) {
        // Remove screenshot data before storing to save space if it's too large
        if (eventData.screenshot && eventData.screenshot.length > 1000) {
            eventData.screenshot = 'data:image/jpeg;base64,/9j/4AAQ...(truncated)';
            eventData.screenshot_truncated = true;
        }
        
        eventRetryQueue.push(eventData);
        
        // Save to localStorage for persistence
        try {
            localStorage.setItem('proctoring_retry_queue', JSON.stringify(eventRetryQueue));
        } catch (e) {
            console.error('Error saving retry queue:', e);
            // If localStorage is full, clear it and try again with only most recent events
            if (e.name === 'QuotaExceededError') {
                localStorage.clear();
                const recentEvents = eventRetryQueue.slice(-10); // Keep only recent events
                localStorage.setItem('proctoring_retry_queue', JSON.stringify(recentEvents));
                eventRetryQueue = recentEvents;
            }
        }
        
        // If this is the first item, start the retry process
        if (eventRetryQueue.length === 1) {
            setTimeout(processRetryQueue, 5000);
        }
    }
    
    // FIXED: Process retry queue with correct URL
    async function processRetryQueue() {
        if (eventRetryQueue.length === 0) return;
        
        const event = eventRetryQueue[0];
        
        try {
            // FIXED: Use the correct URL with proper prefix
            const response = await fetch('/student/api/proctoring/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify(event),
                signal: AbortSignal.timeout(8000) // 8 second timeout
            });
            
            if (response.ok) {
                // Success! Remove from queue
                eventRetryQueue.shift();
                console.log('Successfully retried logging event');
                
                // Update localStorage
                localStorage.setItem('proctoring_retry_queue', JSON.stringify(eventRetryQueue));
            } else {
                console.error('Retry failed:', await response.text());
            }
        } catch (error) {
            console.error('Error during retry:', error);
        }
        
        // If there are more items or this one failed, try again later
        if (eventRetryQueue.length > 0) {
            // Exponential backoff - wait longer between retries
            const delay = Math.min(10000 + (eventRetryQueue.length * 2000), 30000);
            setTimeout(processRetryQueue, delay);
        }
    }
    
    // Enhanced warning message function
    function showWarning(text) {
        console.log(`Showing warning: ${text}`);
        
        const warningElement = document.getElementById('warning-message');
        const warningText = document.getElementById('warning-text');
        
        if (!warningElement || !warningText) {
            console.error('Warning elements not found in DOM');
            return;
        }
        
        warningText.textContent = text;
        warningElement.style.display = 'block';
        
        // Make warning more visible
        warningElement.style.zIndex = '10000';
        
        // Add shaking animation for emphasis
        warningElement.style.animation = 'shake 0.5s';
        warningElement.style.animationIterationCount = '3';
        
        // Add CSS if not already present
        if (!document.getElementById('warning-animation-style')) {
            const style = document.createElement('style');
            style.id = 'warning-animation-style';
            style.textContent = `
                @keyframes shake {
                    0% { transform: translate(-50%, -50%) rotate(0deg); }
                    10% { transform: translate(-51%, -50%) rotate(-1deg); }
                    20% { transform: translate(-49%, -50%) rotate(1deg); }
                    30% { transform: translate(-51%, -50%) rotate(0deg); }
                    40% { transform: translate(-49%, -50%) rotate(1deg); }
                    50% { transform: translate(-51%, -50%) rotate(-1deg); }
                    60% { transform: translate(-49%, -50%) rotate(0deg); }
                    70% { transform: translate(-51%, -50%) rotate(-1deg); }
                    80% { transform: translate(-49%, -50%) rotate(1deg); }
                    90% { transform: translate(-51%, -50%) rotate(0deg); }
                    100% { transform: translate(-50%, -50%) rotate(0deg); }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Play warning sound if available
        try {
            const warningSound = new Audio('/static/sounds/warning.mp3');
            warningSound.play().catch(e => console.error('Could not play warning sound:', e));
        } catch (e) {
            console.error('Error playing warning sound:', e);
        }
        
        // Hide warning after 5 seconds
        setTimeout(() => {
            warningElement.style.display = 'none';
        }, 5000);
    }
    
    // Dismiss warning
    window.dismissWarning = function() {
        const warningElement = document.getElementById('warning-message');
        if (warningElement) {
            warningElement.style.display = 'none';
        }
    };
    
    // IMPROVED: Monitor tab switching with better logging
    document.addEventListener('visibilitychange', () => {
        const now = new Date();
        
        if (document.hidden) {
            tabSwitchCount++;
            lastTabSwitchTime = now;
            
            console.log(`Tab switch detected (#${tabSwitchCount}). Logging to server...`);
            
            // Immediately log when user switches away - with FIXED URL
            logProctoringEvent(
                'tab_switch', 
                `User switched away from exam tab (occurrence #${tabSwitchCount})`,
                null // No screenshot possible when tab is not visible
            );
            
            // If it's a recurring issue, log a violation
            if (tabSwitchCount >= 3) {
                logProctoringEvent(
                    'serious_violation',
                    `User has switched tabs ${tabSwitchCount} times during the exam`,
                    null
                );
            }
            
            showWarning('Tab switching detected! Please return to the exam immediately.');
        } else if (lastTabSwitchTime) {
            // Calculate time away from tab
            const timeAway = (now - lastTabSwitchTime) / 1000; // in seconds
            
            // Take screenshot when user returns
            setTimeout(() => {
                if (canvas && video) {
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const screenshot = canvas.toDataURL('image/jpeg', 0.7);
                    
                    // Log the return with time information - with FIXED URL
                    logProctoringEvent(
                        'tab_switch_return', 
                        `User returned after ${timeAway.toFixed(1)} seconds away from exam tab (switch #${tabSwitchCount})`,
                        screenshot
                    );
                }
            }, 1000);
            
            lastTabSwitchTime = null;
        }
    });
    
    // Initialize proctoring on page load
    console.log('Initializing proctoring system...');
    setupProctoring();
});

// FIXED: Update the submit exam function to use the correct endpoint
function submitExam() {
    // Disable navigation buttons during submission
    document.getElementById('prev-btn').disabled = true;
    document.getElementById('next-btn').disabled = true;
    document.getElementById('submit-btn').disabled = true;
    
    // Format answers object properly for submission
    const formattedAnswers = {};
    for (const questionId in answers) {
        // Make sure we're sending just the clean question ID as an integer
        const cleanQuestionId = questionId.toString().replace('question_', '');
        formattedAnswers[cleanQuestionId] = answers[questionId];
    }
    
    // Show loading indicator
    const submitBtn = document.getElementById('submit-btn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
    
    // Log the submission attempt
    console.log('Submitting exam with session ID:', sessionId);
    console.log('Formatted answers:', formattedAnswers);
    
    // FIXED: Submit exam with CORRECT ENDPOINT URL
    fetch('/student/api/exam/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify({
            session_id: sessionId,
            answers: formattedAnswers
        })
    })
    .then(response => {
        console.log('Server response status:', response.status);
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`Server returned ${response.status}: ${text || response.statusText}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Submission response:', data);
        if (data.status === 'success') {
            // Remove saved answers
            localStorage.removeItem('exam_' + sessionId + '_answers');
            
            // Show result
            alert('Exam submitted successfully! Your score: ' + data.score);
            
            // Redirect to dashboard
            window.location.href = '/student/dashboard';
        } else {
            alert('Error submitting exam: ' + data.message);
            // Re-enable buttons in case of error
            document.getElementById('prev-btn').disabled = false;
            document.getElementById('next-btn').disabled = false;
            document.getElementById('submit-btn').disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error submitting exam: ' + error.message);
        
        // Re-enable buttons
        document.getElementById('prev-btn').disabled = false;
        document.getElementById('next-btn').disabled = false;
        document.getElementById('submit-btn').disabled = false;
        submitBtn.innerHTML = originalBtnText;
    });
}