<?php 
	session_start();

	require 'funcition.php';

	// cek apakah yang mengakses halaman ini sudah login
	if($_SESSION['level']==""){
		header("location:index.php?pesan=gagal");
	}
	
	$mahasiswa = query("SELECT * FROM soal");

	?>
<!DOCTYPE html>
<html>
<head>
	<link rel="icon" href="icon/hexagonos.jpg">
	<title>Ujian Test</title>
	<link rel="stylesheet" href="assets/css/bootstrap.min.css">
	<script type="text/javascript" src="assets/fontawesome/js/all.js"></script>
</head>
<body>
	
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">

  <img src="icon/1.png" width="10%" class="navbar-brand">
  <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarText" aria-controls="navbarText" aria-expanded="false" aria-label="Toggle navigation">
    <span class="navbar-toggler-icon"></span>
  </button>
  <div class="collapse navbar-collapse" id="navbarText">
    <ul class="navbar-nav mr-auto">
      <li class="nav-item active">
        <a class="nav-link" href="#">Soal </a>
      </li>
      <li class="nav-item">
        <a class="nav-link" href="data_siswa.php">User</a>
      </li>
    </ul>
    <form class="form-inline">
    <a href="logout.php" class="btn btn-outline-danger"><i class="fas fa-sign-out-alt"></i> Logout</a>
  </form>
  </div>
</nav>
	<br>
	

<div class="container">
	<div class="alert alert-success alert-dismissible fade show text-center" role="alert">
	  Halo <strong><?php echo strtoupper($_SESSION['username']); ?></strong> Anda telah login
	  <button type="button" class="close" data-dismiss="alert" aria-label="Close">
	    <span aria-hidden="true">&times;</span>
	  </button>
	</div>
		<a href="tambah.php" class="btn btn-primary mt-5 " ><i class="fas fa-plus"></i> Tambah Soal</a>

<div class="card mt-2 mb-2">
	
 <table class="table table-striped ">
	<thead class="bg-primary text-white">
	<tr>
		<th >No</th>
		<th width="72%">Pertanyaan</th>
		<th >View</th>
		<th >Aksi</th>
	</tr>
</thead>
<tbody>
<?php $i = 1; ?>
<?php foreach ($mahasiswa as $row) :?>
	<tr>
		<td><?=$i; ?></td>
		<td><?=$row["soal"]; ?></td>
		<td><a href="view.php?id=<?=$row["id"]; ?>" class="btn btn-primary" ><i class="fas fa-eye"></i></td>
		<td>
			<a href="ubah.php?id=<?=$row["id"]; ?>" class="btn btn-success"><i class="fas fa-edit"></i> Edit</a>
			<a href="hapus.php?id=<?=$row["id"]; ?>" class="btn btn-danger" onclick="return confirm('yakin');"><i class="fas fa-trash-alt"></i> Hapus</a>
		</td>
	</tr>
	<?php $i++; ?>
<?php endforeach; ?>
</tbody>
</table>
</div>


</div>
<!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="assets/jquery-3.4.1.slim.min.js" ></script>
    <script src="assets/popper.min.js" ></script>
    <script src="assets/js/bootstrap.min.js" ></script>
</body>
</html>

