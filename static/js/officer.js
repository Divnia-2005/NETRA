// officer.js
// Purpose: Handle Officer Dashboard actions

console.log("Officer dashboard JS loaded");

// ---------------- LOGOUT ----------------
function logoutOfficer() {
    window.location.href = "/logout";
}

// ---------------- ALERT ACTIONS (PLACEHOLDER) ----------------
// These are ready for backend integration later

function acknowledgeAlert(alertId) {
    console.log("Acknowledged alert:", alertId);

    // Future backend call
    // fetch(`/officer/alert/${alertId}/ack`, { method: "POST" })
}

function dismissAlert(alertId) {
    console.log("Dismissed alert:", alertId);

    // Future backend call
    // fetch(`/officer/alert/${alertId}/dismiss`, { method: "POST" })
}

// ---------------- PAGE LOAD ----------------
document.addEventListener("DOMContentLoaded", () => {
    console.log("Officer dashboard ready");
});
