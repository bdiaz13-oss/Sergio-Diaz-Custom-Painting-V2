// script.js - navbar shrink/grow on hover for dashboard

document.addEventListener('DOMContentLoaded', function() {
  const navbar = document.querySelector('.navbar');
  let isShrunk = false;

  function shrinkNavbar() {
    if (!isShrunk) {
      navbar.style.transition = 'all 0.3s';
      navbar.style.paddingTop = '2px';
      navbar.style.paddingBottom = '2px';
      navbar.style.minHeight = '36px';
      isShrunk = true;
    }
  }

  function growNavbar() {
    if (isShrunk) {
      navbar.style.transition = 'all 0.3s';
      navbar.style.paddingTop = '';
      navbar.style.paddingBottom = '';
      navbar.style.minHeight = '';
      isShrunk = false;
    }
  }

  // Shrink when mouse leaves top 60px, grow when mouse enters
  document.addEventListener('mousemove', function(e) {
    if (e.clientY < 60) {
      growNavbar();
    } else {
      shrinkNavbar();
    }
  });

  // Also grow on focus (keyboard nav)
  navbar.addEventListener('focusin', growNavbar);
  navbar.addEventListener('focusout', shrinkNavbar);
});
