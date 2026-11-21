document.addEventListener("DOMContentLoaded", function () {
  const emailField =
    document.getElementById("email") ||
    document.querySelector("input[name='email']");
  const passwordField =
    document.getElementById("password") ||
    document.querySelector("input[name='password']");
  const fillButtons = document.querySelectorAll(".demo-fill-btn");

  fillButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      const email = this.getAttribute("data-email");
      const password = this.getAttribute("data-password");
      if (emailField && passwordField) {
        emailField.value = email;
        passwordField.value = password;
        emailField.dispatchEvent(new Event("input", { bubbles: true }));
        passwordField.dispatchEvent(new Event("input", { bubbles: true }));
        passwordField.focus();
      }
    });
  });
});
