// SC Component Tracker — global JS utilities

// Auto-dismiss alerts after 4 seconds
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert.alert-success, .alert.alert-info").forEach(el => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 4000);
  });
});
