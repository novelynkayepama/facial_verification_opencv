/* ================================
   LOGIN CHECK FOR LOAN APPLICATION
================================ */

function applyLoan() {
    const loggedIn = localStorage.getItem("loggedIn");

    if (!loggedIn) {
        alert("Please login first to apply for a loan.");
        window.location.href = "login.html";
    } else {
        window.location.href = "facial_verification.html";
    }
}

/* ================================
   LOGOUT FUNCTION (OPTIONAL)
================================ */

function logout() {
    localStorage.removeItem("loggedIn");
    alert("You have been logged out.");
    window.location.href = "index.html";
}
