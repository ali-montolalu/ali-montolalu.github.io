	<?php 
	if(isset($_GET['pesan'])){
		if($_GET['pesan']=="gagal"){
			echo "<div class='alert'>Username dan Password tidak sesuai !</div>";
		}
	}
	?>
<!doctype html>
<html lang="en">
  <head>
  <link rel="icon" href="icon/hexagonos.jpg"> 
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="assets/css/bootstrap.min.css">
    <script type="text/javascript" src="assets/fontawesome/js/all.js"></script>
    <link rel="stylesheet" type="text/css" href="assets/style.css">

    <title>Ujian Test</title>
  </head>
  <body id='header' class='header ignielPelangi'>
 
 <?php if(isset($error)): ?>
	<p style="color: red; font-style: italic;">üsername / password salah</p>
<?php endif; ?>
<div class="posisi" id="posisi">
<div class="container">
	<div class="row justify-content-center">
		<div class="col col-4">
			<div class="card">
	            <div  class="card-header bg-transparent" id="header">
	                <h1 >LOGIN</h1>
	            </div>
			    <form action="cek_login.php" method="post" enctype="multipart/form-data">
			    	<div class="card-body">
			    		
						<div class="form-group ">
			    			<div class="input-group">
						        <div class="input-group-prepend" >
						          <div class="input-group-text bg-transparent" ><i class="fas fa-user "></i></div>
						        </div>
					        		<input type="text" class="form-control" name="username" id="username" placeholder="username" autocomplete="off"></input>
				      		</div>
			  			</div>
						<div class="form-group ">
						    <div class="input-group">
						        <div class="input-group-prepend">
						          <div class="input-group-text bg-transparent"><i class="fas fa-lock"></i></div>
						        </div>
						    <input type="password" class="form-control" name="password" id="password" placeholder="password"></input>
						    </div>
						</div>
						<div class="card-footer bg-transparent " id="footer">
							<div class="row justify-content-center">
						 	
			  				<button type="submit" name="login" class="btn btn-primary text-white col col-12">Login</button>
			  				</div>
			  			</div>
			  		</div>
				</form>
			</div>
		</div>
	</div>
</div>
</div>

    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="assets/jquery-3.4.1.slim.min.js" ></script>
    <script src="assets/popper.min.js" ></script>
    <script src="assets/js/bootstrap.min.js"></script>

</body>
</html>