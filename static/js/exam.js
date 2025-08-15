document.addEventListener('DOMContentLoaded', function() {
    // Exam variables
    const examDuration = parseInt(document.getElementById('exam-duration').value);
    const sessionId = document.getElementById('session-id').value;
    const questionCount = document.querySelectorAll('.question-card').length;
    let currentQuestion = 0;
    let answers = {};
    let timeLeft = examDuration * 60; // in seconds
    let timer;
    
    // Initialize exam
    function initExam() {
        // Show first question
        showQuestion(0);
        
        // Start timer
        startTimer();
        
        // Save answers to local storage every 10 seconds
        setInterval(saveAnswersToLocalStorage, 10000);
        
        // Restore answers from local storage if any
        restoreAnswersFromLocalStorage();
        
        // Add event listeners to radio buttons
        setupRadioListeners();
        
        // Try to enter full-screen mode
        if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen().catch(err => {
                console.error('Error attempting to enable full-screen mode:', err);
            });
        }
    }
    
    // Show specific question
    window.showQuestion = function(index) {
        // Hide all questions
        document.querySelectorAll('.question-card').forEach(q => {
            q.style.display = 'none';
        });
        
        // Remove current class from all nav buttons
        document.querySelectorAll('.question-btn').forEach(btn => {
            btn.classList.remove('current');
        });
        
        // Show selected question
        const questionElements = document.querySelectorAll('.question-card');
        if (index >= 0 && index < questionElements.length) {
            questionElements[index].style.display = 'block';
            currentQuestion = index;
            
            // Add current class to current question button
            document.querySelectorAll('.question-btn')[index].classList.add('current');
            
            // Update prev/next button states
            updateNavigationButtons();
        }
    };
    
    // Navigate between questions
    window.navigateQuestion = function(direction) {
        const newIndex = currentQuestion + direction;
        if (newIndex >= 0 && newIndex < questionCount) {
            showQuestion(newIndex);
        }
    };
    
    // Update navigation buttons
    function updateNavigationButtons() {
        document.getElementById('prev-btn').disabled = (currentQuestion === 0);
        document.getElementById('next-btn').disabled = (currentQuestion === questionCount - 1);
    }
    
    // Set up listeners for radio buttons
    function setupRadioListeners() {
        document.querySelectorAll('input[type="radio"]').forEach(radio => {
            radio.addEventListener('change', function() {
                const questionId = this.name.split('_')[1];
                const selectedOption = this.value;
                
                // Store answer
                answers[questionId] = selectedOption;
                
                // Mark question as answered in navigation
                const questionIndex = Array.from(document.querySelectorAll('.question-card')).findIndex(
                    q => q.id === `question-${questionId}`
                );
                document.querySelectorAll('.question-btn')[questionIndex].classList.add('answered');
                
                // Save to local storage
                saveAnswersToLocalStorage();
            });
        });
    }
    
    // Start the exam timer
    function startTimer() {
        const timerElement = document.getElementById('timer');
        
        timer = setInterval(() => {
            timeLeft--;
            
            // Format time
            const hours = Math.floor(timeLeft / 3600);
            const minutes = Math.floor((timeLeft % 3600) / 60);
            const seconds = timeLeft % 60;
            
            timerElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            // Check if time is running out
            if (timeLeft <= 300) { // Last 5 minutes
                timerElement.classList.add('blink');
            }
            
            // Check if time is up
            if (timeLeft <= 0) {
                clearInterval(timer);
                submitExam();
            }
        }, 1000);
    }
    
    // Save answers to local storage
    function saveAnswersToLocalStorage() {
        localStorage.setItem(`exam_${sessionId}_answers`, JSON.stringify(answers));
    }
    
    // Restore answers from local storage
    function restoreAnswersFromLocalStorage() {
        const savedAnswers = localStorage.getItem(`exam_${sessionId}_answers`);
        if (savedAnswers) {
            answers = JSON.parse(savedAnswers);
            
            // Restore selected options
            for (const questionId in answers) {
                const selectedOption = answers[questionId];
                const radioBtn = document.getElementById(`option_${selectedOption}_${questionId}`);
                if (radioBtn) {
                    radioBtn.checked = true;
                    
                    // Mark question as answered in navigation
                    const questionIndex = Array.from(document.querySelectorAll('.question-card')).findIndex(
                        q => q.id === `question-${questionId}`
                    );
                    document.querySelectorAll('.question-btn')[questionIndex].classList.add('answered');
                }
            }
        }
    }
    
    // Confirm exam submission
    window.confirmSubmit = function() {
        const answered = Object.keys(answers).length;
        const message = `You have answered ${answered} out of ${questionCount} questions. Are you sure you want to submit your exam?`;
        
        if (confirm(message)) {
            submitExam();
        }
    };
    
    // Submit exam to server
    async function submitExam() {
        try {
            const response = await fetch('/api/exam/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    answers: answers
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Clear local storage
                localStorage.removeItem(`exam_${sessionId}_answers`);
                
                // Show results
                alert(`Exam submitted successfully! Your score: ${result.score}`);
                
                // Redirect to dashboard
                window.location.href = '/student/dashboard';
            } else {
                alert('Error submitting exam: ' + result.message);
            }
        } catch (error) {
            console.error('Error submitting exam:', error);
            alert('Failed to submit exam. Please try again.');
        }
    }
    
    // Prevent page refresh or navigation
    window.addEventListener('beforeunload', function(e) {
        // If exam is not yet submitted
        const message = 'Are you sure you want to leave? Your exam progress will be lost!';
        e.returnValue = message;
        return message;
    });
    
    // Initialize when page loads
    initExam();
});