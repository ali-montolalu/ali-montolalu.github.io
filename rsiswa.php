<?php 
// session_start();

// // cek apakah yang mengakses halaman ini sudah login
// 	if($_SESSION['level']==""){
// 		header("location:index.php?pesan=gagal");
// 	}
require 'funcition.php';

if(isset($_POST["register"])){
	if(registrasi($_POST) > 0){
		echo "<script>
				alert('user baru berhasil ditambahkan');
			  </script>";
	} else {
		echo mysqli_error($conn);
	}
}

 ?>

<!doctype html>
<html lang="en">
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="assets/css/bootstrap.min.css">
    <link rel="icon" href="icon/hexagonos.jpg">
	<title>Ujian Test</title>
  </head>
  <body class="bg-gradient-primary">

<?php if(isset($error)): ?>
	<p style="color: red; font-style: italic;">üsername / password salah</p>
<?php endif; ?>

<div class="container">
	<div class="row justify-content-center">
		<div class="col col-5">
			<div class="card mt-5 ">
		    <form action="" method="post" enctype="multipart/form-data">
		    	<div class="card-body">
					<div class="form-group ">
		    			<label for="username">Username</label>
		    			<input type="text" class="form-control" name="username" id="username" autocomplete="off"></input>
		  			</div>
					<div class="form-group ">
					    <label for="password">Password</label>
					    <input type="password" class="form-control" name="password" id="password"></input>
					 </div>
					 <div class="form-group ">
					    <label for="password2">Password</label>
					    <input type="password" class="form-control" name="password2" id="password2"></input>
					 </div>
					 <div class="form-group">
					    <label for="level">Level</label>
					    <select class="form-control" id="level" name="level">
					      	<option >admin</option>
							<option >siswa</option>
					    </select>
					  </div>
					  </div>
					  <div class="card-footer">
					 	<a href="data_siswa.php" class="btn btn-dark ">Back</a> 
		  				<button type="submit" name="register" class="btn btn-primary ">Confirm</button>
		  				</div>
		  		
			</form>
			</div>
		</div>
	</div>
</div>

    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="assets/jquery-3.4.1.slim.min.js" ></script>
    <script src="assets/popper.min.js" ></script>
    <script src="assets/js/bootstrap.min.js" ></script>
  </body>
</html>